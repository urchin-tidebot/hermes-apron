package server

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/apron-chat/apron-server-go/apron"
	"github.com/apron-chat/apron-server-go/store"
	"github.com/coder/websocket"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"
)

type failStore struct {
	store.Store
	fail      atomic.Bool
	committed bool
}

func (f *failStore) Apply(batch []store.Entry) error {
	for _, e := range batch {
		if e.Kind == "user" && f.fail.Load() {
			return errors.New("injected write failure")
		}
		if e.Kind == "user" {
			f.committed = true
		}
	}
	return f.Store.Apply(batch)
}

func TestEnrollmentFailureAtomicAcrossRestart(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.db")
	st, err := store.OpenSQLite(path)
	if err != nil {
		t.Fatal(err)
	}
	f := &failStore{Store: st}
	s, h, e := enrollmentServer(t, func(c *apron.Config) { c.Store = f })
	token, err := e.policy.Issue(time.Minute, false)
	if err != nil {
		t.Fatal(err)
	}
	w := dial(t, h.URL)
	a := authn(t)
	o := begin(t, w, "register", token)
	f.fail.Store(true)
	// Enrollment failure must close transport or answer error, never success.
	raw := a.registration(t, o, origin, "localhost", 0x45)
	request, _ := json.Marshal(map[string]any{"method": "auth", "id": "failure", "params": map[string]any{"scheme": "webauthn", "action": "register", "step": "finish", "challenge_id": o["challenge_id"], "credential": raw}})
	if err = w.c.Write(w.ctx, websocket.MessageText, request); err != nil {
		t.Fatal(err)
	}
	for {
		_, body, readErr := w.c.Read(w.ctx)
		if readErr != nil {
			break
		}
		var frame map[string]any
		json.Unmarshal(body, &frame)
		if frame["result"] != nil {
			t.Fatal("enrollment acknowledged failed persistence")
		}
	}
	w.c.CloseNow()
	h.Close()
	s.Shutdown(context.Background())
	next, err := store.OpenSQLite(path)
	if err != nil {
		t.Fatal(err)
	}
	users := 0
	if err = next.Load(func(e store.Entry) error {
		if e.Kind == "user" {
			users++
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if users != 0 {
		t.Fatal("half-created account persisted")
	}
	_, h2, _ := enrollmentServer(t, func(c *apron.Config) { c.Store = next })
	w2 := dial(t, h2.URL)
	o = begin(t, w2, "register", token)
	result(t, finish(t, w2, "register", o, a.registration(t, o, origin, "localhost", 0x45)))
}

func TestRestartPreservesIdentityAndRevocation(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.db")
	open := func(c *apron.Config) {
		var err error
		c.Store, err = store.OpenSQLite(path)
		if err != nil {
			t.Fatal(err)
		}
	}
	s, h, e := enrollmentServer(t, open)
	token, err := e.policy.Issue(time.Minute, true)
	if err != nil {
		t.Fatal(err)
	}
	w := dial(t, h.URL)
	a := authn(t)
	o := begin(t, w, "register", token)
	r := result(t, finish(t, w, "register", o, a.registration(t, o, origin, "localhost", 0x45)))
	id := r["you"].(map[string]any)["user_id"].(string)
	w.c.CloseNow()
	h.Close()
	s.Shutdown(context.Background())
	s2, h2, e2 := enrollmentServer(t, open)
	other := dial(t, h2.URL)
	o = begin(t, other, "login", "")
	r = result(t, finish(t, other, "login", o, a.assertion(t, o)))
	if r["you"].(map[string]any)["user_id"] != id {
		t.Fatal("identity changed after restart")
	}
	if err = e2.policy.RevokeAccount(id); err != nil {
		t.Fatal(err)
	}
	other.c.CloseNow()
	h2.Close()
	s2.Shutdown(context.Background())
	_, h3, _ := enrollmentServer(t, open)
	denied(t, dial(t, h3.URL).call(t, "auth", map[string]any{"scheme": "token", "token": r["token"]}))
	login := dial(t, h3.URL)
	o = begin(t, login, "login", "")
	denied(t, finish(t, login, "login", o, a.assertion(t, o)))
}
