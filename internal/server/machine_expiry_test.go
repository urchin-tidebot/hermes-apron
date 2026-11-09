package server

import (
	"context"
	"crypto/rand"
	"encoding/json"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"

	"github.com/apron-chat/apron-server-go/apron"
	"github.com/apron-chat/apron-server-go/store"
	"github.com/coder/websocket"
)

func expectMachineClosed(t *testing.T, w *wire) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	for {
		_, _, err := w.c.Read(ctx)
		if err != nil {
			if ctx.Err() != nil {
				t.Fatal("machine expiry left an authenticated socket alive")
			}
			return
		}
	}
}

func TestMachineExpiryClosesAllSocketsAndQueuedFrames(t *testing.T) {
	entered, release := make(chan struct{}), make(chan struct{})
	released := false
	defer func() {
		if !released {
			close(release)
		}
	}()
	e := &enrolling{machine: rand.Text() + rand.Text(), ttl: 600 * time.Millisecond}
	e.filter = func(ctx context.Context, d *apron.Draft) error {
		if d.Text() == "queued before expiry" {
			close(entered)
			select {
			case <-release:
			case <-ctx.Done():
			}
		}
		return nil
	}
	_, h, _ := enrollmentServer(t, func(c *apron.Config) { c.Extensions = []apron.Extension{e} })
	invite, err := e.policy.Issue(time.Minute, false)
	if err != nil {
		t.Fatal(err)
	}
	human := dial(t, h.URL)
	a := authn(t)
	o := begin(t, human, "register", invite)
	result(t, finish(t, human, "register", o, a.registration(t, o, origin, "localhost", 0x45)))
	one, two := dial(t, h.URL), dial(t, h.URL)
	for _, w := range []*wire{one, two} {
		result(t, w.call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
	}
	for i, text := range []string{"queued before expiry", "pipelined after expiry"} {
		frame, _ := json.Marshal(map[string]any{"id": string(rune('a' + i)), "method": "message", "params": map[string]any{"room_id": "general", "body": map[string]any{"text": text}}})
		if err = one.c.Write(one.ctx, websocket.MessageText, frame); err != nil {
			t.Fatal(err)
		}
	}
	select {
	case <-entered:
	case <-time.After(time.Second):
		t.Fatal("filter not entered before expiry")
	}
	// This is a genuine clock wait on an otherwise idle second socket.
	expectMachineClosed(t, two)
	close(release)
	released = true
	expectMachineClosed(t, one)
	denied(t, dial(t, h.URL).call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
	history := result(t, human.call(t, "history", map[string]any{"room_id": "general"}))
	messages, _ := history["messages"].([]any)
	for _, v := range messages {
		m := v.(map[string]any)
		if from, ok := m["from"].(map[string]any); ok && from["user_id"] == "hermes" {
			t.Fatal("expired queued machine frame committed")
		}
	}
}

func TestMachineExpiryAcrossRestart(t *testing.T) {
	path := filepath.Join(t.TempDir(), "expiry.db")
	token := rand.Text() + rand.Text()
	open := func(ttl time.Duration) (*apron.Server, *httptest.Server, *enrolling) {
		e := &enrolling{machine: token, ttl: ttl}
		s, h, _ := enrollmentServer(t, func(c *apron.Config) {
			c.Extensions = []apron.Extension{e}
			var err error
			c.Store, err = store.OpenSQLite(path)
			if err != nil {
				t.Fatal(err)
			}
		})
		return s, h, e
	}
	s, h, _ := open(700 * time.Millisecond)
	s.Shutdown(context.Background())
	h.Close()
	s, h, _ = open(time.Hour) // Binding the same token must retain its original deadline.
	w := dial(t, h.URL)
	result(t, w.call(t, "auth", map[string]any{"scheme": "token", "token": token}))
	expectMachineClosed(t, w)
	s.Shutdown(context.Background())
	h.Close()
	_, h, _ = open(time.Hour)
	denied(t, dial(t, h.URL).call(t, "auth", map[string]any{"scheme": "token", "token": token}))
}
