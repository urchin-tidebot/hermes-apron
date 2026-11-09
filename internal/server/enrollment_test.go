package server

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"testing"
	"time"

	"github.com/apron-chat/apron-server-go/apron"
	"github.com/apron-chat/apron-server-go/store"
	"github.com/go-webauthn/webauthn/webauthn"
)

type enrolling struct {
	policy  *apron.Enrollment
	machine string
	rooms   []string
	ttl     time.Duration
}

func (*enrolling) Name() string { return "closed" }
func (e *enrolling) Init(r *apron.Registrar) (err error) {
	e.policy, err = r.ClosedEnrollment()
	if err == nil && e.machine != "" {
		_, err = r.Bot("hermes", apron.BotOptions{Name: "Hermes"})
		if err == nil {
			if e.rooms == nil {
				e.rooms = []string{"general"}
			}
			if e.ttl == 0 {
				e.ttl = time.Hour
			}
			err = e.policy.BindMachine("hermes", e.machine, e.ttl, e.rooms)
		}
	}
	return
}

func TestInvitationVerifierOnly(t *testing.T) {
	cfg := SecureConfig()
	ext := &enrolling{}
	cfg.Extensions = []apron.Extension{ext}
	w, err := webauthn.New(&webauthn.Config{RPID: "localhost", RPDisplayName: "Test", RPOrigins: []string{"http://localhost"}})
	if err != nil {
		t.Fatal(err)
	}
	cfg.WebAuthn = w
	cfg.UploadDir = t.TempDir()
	st := store.NewMemory()
	cfg.Store = st
	s, err := apron.Open(cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Shutdown(context.Background())
	token, err := ext.policy.Issue(5*time.Minute, true)
	if err != nil {
		t.Fatal(err)
	}
	if len(token) < 43 {
		t.Fatal("invitation must contain at least 256 random bits")
	}
	hash := sha256.Sum256([]byte(token))
	found := false
	if err := st.Load(func(e store.Entry) error {
		if strings.Contains(string(e.Value), token) {
			t.Fatal("plaintext invitation persisted")
		}
		if strings.Contains(string(e.Value), hex.EncodeToString(hash[:])) {
			found = true
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if !found {
		t.Fatal("durable invitation verifier missing")
	}
}
