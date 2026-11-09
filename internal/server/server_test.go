package server

import (
	"context"
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/apron-chat/apron-server-go/apron"
	"github.com/coder/websocket"
	"github.com/go-webauthn/webauthn/webauthn"
)

func TestFreshServerClosed(t *testing.T) {
	cfg := SecureConfig()
	w, err := webauthn.New(&webauthn.Config{RPID: "localhost", RPDisplayName: "Test", RPOrigins: []string{"http://localhost"}})
	if err != nil {
		t.Fatal(err)
	}
	cfg.WebAuthn = w
	cfg.UploadDir = t.TempDir()
	cfg.OriginPatterns = []string{"http://localhost"}
	s, err := apron.Open(cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Shutdown(context.Background())
	h := httptest.NewServer(s)
	defer h.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	c, _, err := websocket.Dial(ctx, "ws"+strings.TrimPrefix(h.URL, "http")+"/ws", &websocket.DialOptions{HTTPHeader: map[string][]string{"Origin": {"http://localhost"}}})
	if err != nil {
		t.Fatal(err)
	}
	defer c.CloseNow()
	_, raw, err := c.Read(ctx)
	if err != nil {
		t.Fatal(err)
	}
	var frame map[string]any
	if err = json.Unmarshal(raw, &frame); err != nil {
		t.Fatal(err)
	}
	p := frame["params"].(map[string]any)
	if signup, ok := p["signup"].([]any); !ok || len(signup) != 0 {
		t.Fatal("closed enrollment advertises open signup")
	}
	for _, scheme := range p["auth"].([]any) {
		if scheme == "guest" || scheme == "email" || scheme == "external" {
			t.Fatalf("fresh server offers forbidden scheme %s", scheme)
		}
	}
	for _, method := range []string{"room_list", "history", "status", "message"} {
		raw, _ = json.Marshal(map[string]any{"id": method, "method": method, "params": map[string]any{}})
		if err = c.Write(ctx, websocket.MessageText, raw); err != nil {
			t.Fatal(err)
		}
		_, raw, err = c.Read(ctx)
		if err != nil {
			t.Fatal(err)
		}
		json.Unmarshal(raw, &frame)
		if frame["error"] == nil {
			t.Fatalf("unauthenticated %s leaked data", method)
		}
	}
}
