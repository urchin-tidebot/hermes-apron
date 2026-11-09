package server

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"github.com/apron-chat/apron-server-go/apron"
	"github.com/coder/websocket"
	"github.com/fxamacker/cbor/v2"
	"github.com/go-webauthn/webauthn/webauthn"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"
)

const origin = "http://localhost"

type wire struct {
	c   *websocket.Conn
	ctx context.Context
	n   int
}

func dial(t *testing.T, url string) *wire {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	t.Cleanup(cancel)
	c, _, err := websocket.Dial(ctx, "ws"+strings.TrimPrefix(url, "http")+"/ws", &websocket.DialOptions{HTTPHeader: http.Header{"Origin": {origin}}})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { c.CloseNow() })
	w := &wire{c: c, ctx: ctx}
	w.read(t)
	return w
}
func (w *wire) read(t *testing.T) map[string]any {
	t.Helper()
	_, b, err := w.c.Read(w.ctx)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err = json.Unmarshal(b, &m); err != nil {
		t.Fatal(err)
	}
	return m
}
func (w *wire) call(t *testing.T, method string, p map[string]any) map[string]any {
	t.Helper()
	w.n++
	id := strconv.Itoa(w.n)
	b, _ := json.Marshal(map[string]any{"method": method, "id": id, "params": p})
	if err := w.c.Write(w.ctx, websocket.MessageText, b); err != nil {
		t.Fatal(err)
	}
	for {
		m := w.read(t)
		if m["id"] == id {
			return m
		}
	}
}
func result(t *testing.T, m map[string]any) map[string]any {
	t.Helper()
	r, ok := m["result"].(map[string]any)
	if !ok {
		t.Fatalf("expected result, got %#v", m)
	}
	return r
}
func denied(t *testing.T, m map[string]any) {
	t.Helper()
	if m["error"] == nil {
		t.Fatalf("expected denial, got %#v", m)
	}
}
func begin(t *testing.T, w *wire, action, invite string) map[string]any {
	t.Helper()
	return result(t, w.call(t, "auth", map[string]any{"scheme": "webauthn", "action": action, "step": "begin", "invitation": invite}))
}
func finish(t *testing.T, w *wire, action string, options, credential map[string]any) map[string]any {
	t.Helper()
	return w.call(t, "auth", map[string]any{"scheme": "webauthn", "action": action, "step": "finish", "challenge_id": options["challenge_id"], "credential": credential})
}
func enrollmentServer(t *testing.T, edit func(*apron.Config)) (*apron.Server, *httptest.Server, *enrolling) {
	t.Helper()
	cfg := SecureConfig()
	e := &enrolling{}
	cfg.Extensions = []apron.Extension{e}
	cfg.UploadDir = t.TempDir()
	cfg.OriginPatterns = []string{origin}
	cfg.WebAuthn, _ = webauthn.New(&webauthn.Config{RPID: "localhost", RPDisplayName: "Test", RPOrigins: []string{origin}})
	if edit != nil {
		edit(&cfg)
	}
	s, err := apron.Open(cfg)
	if err != nil {
		t.Fatal(err)
	}
	h := httptest.NewServer(s)
	t.Cleanup(func() { h.Close(); s.Shutdown(context.Background()) })
	return s, h, e
}

// Software authenticator shape adapted from upstream apron/webauthn_test.go,
// MIT, Copyright (c) apron-server-go contributors. Verifies real ES256 signatures.
type authenticator struct {
	key     *ecdsa.PrivateKey
	id      []byte
	handle  string
	counter uint32
}

func authn(t *testing.T) *authenticator {
	k, e := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if e != nil {
		t.Fatal(e)
	}
	return &authenticator{key: k, id: []byte(rand.Text())}
}
func b64(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }
func clientData(kind, challenge, site string) []byte {
	b, _ := json.Marshal(map[string]any{"type": kind, "challenge": challenge, "origin": site, "crossOrigin": false})
	return b
}
func (a *authenticator) registration(t *testing.T, o map[string]any, site, rp string, flags byte) map[string]any {
	p := o["public_key"].(map[string]any)
	a.handle = p["user"].(map[string]any)["id"].(string)
	cose, e := cbor.Marshal(map[int]any{1: 2, 3: -7, -1: 1, -2: a.key.X.FillBytes(make([]byte, 32)), -3: a.key.Y.FillBytes(make([]byte, 32))})
	if e != nil {
		t.Fatal(e)
	}
	hash := sha256.Sum256([]byte(rp))
	data := append(hash[:], flags, 0, 0, 0, 0)
	data = append(data, make([]byte, 16)...)
	data = binary.BigEndian.AppendUint16(data, uint16(len(a.id)))
	data = append(data, a.id...)
	data = append(data, cose...)
	att, e := cbor.Marshal(map[string]any{"fmt": "none", "authData": data, "attStmt": map[string]any{}})
	if e != nil {
		t.Fatal(e)
	}
	return map[string]any{"id": b64(a.id), "rawId": b64(a.id), "type": "public-key", "clientExtensionResults": map[string]any{}, "response": map[string]any{"clientDataJSON": b64(clientData("webauthn.create", p["challenge"].(string), site)), "attestationObject": b64(att)}}
}
func (a *authenticator) assertion(t *testing.T, o map[string]any) map[string]any {
	a.counter++
	p := o["public_key"].(map[string]any)
	client := clientData("webauthn.get", p["challenge"].(string), origin)
	hash := sha256.Sum256([]byte("localhost"))
	data := append(hash[:], 5)
	data = binary.BigEndian.AppendUint32(data, a.counter)
	ch := sha256.Sum256(client)
	signed := sha256.Sum256(append(append([]byte{}, data...), ch[:]...))
	sig, err := ecdsa.SignASN1(rand.Reader, a.key, signed[:])
	if err != nil {
		t.Fatal(err)
	}
	return map[string]any{"id": b64(a.id), "rawId": b64(a.id), "type": "public-key", "response": map[string]any{"clientDataJSON": b64(client), "authenticatorData": b64(data), "signature": b64(sig), "userHandle": a.handle}}
}
func TestInvitedRegistration(t *testing.T) {
	_, h, e := enrollmentServer(t, nil)
	token, err := e.policy.Issue(5*time.Minute, true)
	if err != nil {
		t.Fatal(err)
	}
	w := dial(t, h.URL)
	a := authn(t)
	o := begin(t, w, "register", token)
	r := result(t, finish(t, w, "register", o, a.registration(t, o, origin, "localhost", 0x45)))
	if r["you"].(map[string]any)["user_id"] == nil {
		t.Fatal("missing stable identity")
	}
	other := dial(t, h.URL)
	login := begin(t, other, "login", "")
	again := result(t, finish(t, other, "login", login, a.assertion(t, login)))
	if again["you"].(map[string]any)["user_id"] != r["you"].(map[string]any)["user_id"] {
		t.Fatal("identity changed")
	}
}

func TestConcurrentInvitationAndReplay(t *testing.T) {
	_, h, e := enrollmentServer(t, nil)
	token, err := e.policy.Issue(5*time.Minute, false)
	if err != nil {
		t.Fatal(err)
	}
	w1, w2 := dial(t, h.URL), dial(t, h.URL)
	a1, a2 := authn(t), authn(t)
	o1, o2 := begin(t, w1, "register", token), begin(t, w2, "register", token)
	c1, c2 := a1.registration(t, o1, origin, "localhost", 0x45), a2.registration(t, o2, origin, "localhost", 0x45)
	type outcome struct{ r map[string]any }
	ch := make(chan outcome, 2)
	go func() { ch <- outcome{finish(t, w1, "register", o1, c1)} }()
	go func() { ch <- outcome{finish(t, w2, "register", o2, c2)} }()
	successes := 0
	for range 2 {
		if (<-ch).r["result"] != nil {
			successes++
		}
	}
	if successes != 1 {
		t.Fatalf("got %d accounts for one invitation", successes)
	}
	denied(t, finish(t, w1, "register", o1, c1))
	denied(t, finish(t, w2, "register", o2, c2))
	denied(t, dial(t, h.URL).call(t, "auth", map[string]any{"scheme": "webauthn", "action": "register", "step": "begin", "invitation": token}))
}

func TestForgedCeremonyLeavesInvitationUsable(t *testing.T) {
	for _, tc := range []struct {
		name, site, rp string
		flags          byte
	}{{"origin", "https://evil.example", "localhost", 0x45}, {"rp", origin, "evil.example", 0x45}, {"no-uv", origin, "localhost", 0x41}} {
		t.Run(tc.name, func(t *testing.T) {
			_, h, e := enrollmentServer(t, nil)
			token, err := e.policy.Issue(5*time.Minute, false)
			if err != nil {
				t.Fatal(err)
			}
			w := dial(t, h.URL)
			a := authn(t)
			o := begin(t, w, "register", token)
			denied(t, finish(t, w, "register", o, a.registration(t, o, tc.site, tc.rp, tc.flags)))
			good := begin(t, w, "register", token)
			result(t, finish(t, w, "register", good, a.registration(t, good, origin, "localhost", 0x45)))
		})
	}
}

func TestRevocationClosesPendingInvitation(t *testing.T) {
	_, h, e := enrollmentServer(t, nil)
	token, err := e.policy.Issue(time.Minute, false)
	if err != nil {
		t.Fatal(err)
	}
	w := dial(t, h.URL)
	a := authn(t)
	o := begin(t, w, "register", token)
	hash := sha256.Sum256([]byte(token))
	if err = e.policy.RevokeInvitation(hex.EncodeToString(hash[:])); err != nil {
		t.Fatal(err)
	}
	denied(t, finish(t, w, "register", o, a.registration(t, o, origin, "localhost", 0x45)))
}

func TestAccountRevocationDisconnectsAndRejectsResume(t *testing.T) {
	_, h, e := enrollmentServer(t, nil)
	token, err := e.policy.Issue(time.Minute, false)
	if err != nil {
		t.Fatal(err)
	}
	w := dial(t, h.URL)
	a := authn(t)
	o := begin(t, w, "register", token)
	r := result(t, finish(t, w, "register", o, a.registration(t, o, origin, "localhost", 0x45)))
	id := r["you"].(map[string]any)["user_id"].(string)
	if err = e.policy.RevokeAccount(id); err != nil {
		t.Fatal(err)
	}
	denied(t, dial(t, h.URL).call(t, "auth", map[string]any{"scheme": "token", "token": r["token"]}))
	// A previously verified passkey cannot regain access.
	other := dial(t, h.URL)
	o = begin(t, other, "login", "")
	denied(t, finish(t, other, "login", o, a.assertion(t, o)))
	deadline, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	for {
		_, _, err = w.c.Read(deadline)
		if err != nil {
			break
		}
	}
	if deadline.Err() != nil {
		t.Fatal("revocation did not close active socket")
	}
}

func TestSeparateMachineIdentityRevocable(t *testing.T) {
	cfg := SecureConfig()
	e := &enrolling{machine: rand.Text() + rand.Text()}
	cfg.Extensions = []apron.Extension{e}
	cfg.UploadDir = t.TempDir()
	cfg.OriginPatterns = []string{origin}
	cfg.WebAuthn, _ = webauthn.New(&webauthn.Config{RPID: "localhost", RPDisplayName: "Test", RPOrigins: []string{origin}})
	s, err := apron.Open(cfg)
	if err != nil {
		t.Fatal(err)
	}
	h := httptest.NewServer(s)
	defer s.Shutdown(context.Background())
	defer h.Close()
	w1, w2 := dial(t, h.URL), dial(t, h.URL)
	for _, w := range []*wire{w1, w2} {
		r := result(t, w.call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
		you := r["you"].(map[string]any)
		roles := you["roles"].([]any)
		if you["user_id"] != "hermes" || len(roles) != 1 || roles[0] != "bot" {
			t.Fatal("machine not least privilege bot")
		}
	}
	if err = e.policy.RevokeAccount("hermes"); err != nil {
		t.Fatal(err)
	}
	denied(t, dial(t, h.URL).call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
}

func TestMachineCannotAddHumanPasskey(t *testing.T) {
	cfg := SecureConfig()
	e := &enrolling{machine: rand.Text() + rand.Text()}
	cfg.Extensions = []apron.Extension{e}
	cfg.UploadDir = t.TempDir()
	cfg.OriginPatterns = []string{origin}
	cfg.WebAuthn, _ = webauthn.New(&webauthn.Config{RPID: "localhost", RPDisplayName: "Test", RPOrigins: []string{origin}})
	s, err := apron.Open(cfg)
	if err != nil {
		t.Fatal(err)
	}
	h := httptest.NewServer(s)
	defer s.Shutdown(context.Background())
	defer h.Close()
	w := dial(t, h.URL)
	result(t, w.call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
	denied(t, w.call(t, "auth", map[string]any{"scheme": "webauthn", "action": "register", "step": "begin"}))
}

func TestMachineMustBeJoinedToPost(t *testing.T) {
	cfg := SecureConfig()
	e := &enrolling{machine: rand.Text() + rand.Text()}
	cfg.Extensions = []apron.Extension{e}
	cfg.UploadDir = t.TempDir()
	cfg.OriginPatterns = []string{origin}
	cfg.WebAuthn, _ = webauthn.New(&webauthn.Config{RPID: "localhost", RPDisplayName: "Test", RPOrigins: []string{origin}})
	s, err := apron.Open(cfg)
	if err != nil {
		t.Fatal(err)
	}
	h := httptest.NewServer(s)
	defer s.Shutdown(context.Background())
	defer h.Close()
	w := dial(t, h.URL)
	result(t, w.call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
	room := "general"
	result(t, w.call(t, "room_leave", map[string]any{"room_id": room}))
	denied(t, w.call(t, "message", map[string]any{"room_id": room, "body": map[string]any{"text": "not joined"}}))
}
