package server

import (
	"context"
	"crypto/rand"
	"github.com/apron-chat/apron-server-go/apron"
	"github.com/apron-chat/apron-server-go/store"
	"github.com/coder/websocket"
	"io"
	"net/http"
	"net/http/httptest"
	"net/http/httptrace"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestMachineRoomScope(t *testing.T) {
	e := &enrolling{machine: rand.Text() + rand.Text()}
	path := filepath.Join(t.TempDir(), "scope.db")
	open := func(e *enrolling) (*apron.Server, *httptest.Server) {
		s, h, _ := enrollmentServer(t, func(c *apron.Config) {
			c.Extensions = []apron.Extension{e}
			var err error
			c.Store, err = store.OpenSQLite(path)
			if err != nil {
				t.Fatal(err)
			}
		})
		return s, h
	}
	s, h := open(e)
	invite, err := e.policy.Issue(time.Minute, false)
	if err != nil {
		t.Fatal(err)
	}
	human := dial(t, h.URL)
	a := authn(t)
	o := begin(t, human, "register", invite)
	result(t, finish(t, human, "register", o, a.registration(t, o, origin, "localhost", 0x45)))
	bot := dial(t, h.URL)
	result(t, bot.call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
	public := result(t, human.call(t, "room_set", map[string]any{"title": "Outside public"}))["room_id"].(string)
	private := result(t, human.call(t, "room_set", map[string]any{"title": "Outside private", "private": true}))["room_id"].(string)
	child := result(t, human.call(t, "room_set", map[string]any{"parent_room_id": "general", "title": "Outside thread"}))["room_id"].(string)
	for _, room := range []string{public, private, child} {
		t.Run(room, func(t *testing.T) {
			posted := result(t, human.call(t, "message", map[string]any{"room_id": room, "body": map[string]any{"text": "outside marker", "embeds": []any{map[string]any{"kind": "upload", "name": "fixture.txt", "size": 1}}}}))
			for _, method := range []string{"room_list", "history", "room_join", "room_set"} {
				denied(t, bot.call(t, method, map[string]any{"room_id": room, "typing": 1}))
			}
			denied(t, bot.call(t, "message", map[string]any{"room_id": room, "body": map[string]any{"text": "outside post", "embeds": []any{map[string]any{"kind": "upload", "name": "x", "size": 1}}}}))
			denied(t, bot.call(t, "message", map[string]any{"room_id": "general", "reply_to": map[string]any{"message_id": posted["message_id"]}, "body": map[string]any{"text": "outside reply"}}))
			denied(t, bot.call(t, "room_join", map[string]any{"room_id": room, "user_id": "hermes"}))
		})
	}
	for _, params := range []map[string]any{{"title": "Extra"}, {"title": "Extra private", "private": true}, {"parent_room_id": "general", "title": "Extra thread"}} {
		denied(t, bot.call(t, "room_set", params))
	}
	for _, method := range []string{"room_list", "history"} {
		r := result(t, bot.call(t, method, map[string]any{}))
		for _, key := range []string{"joined", "not_joined", "rooms", "messages"} {
			entries, _ := r[key].([]any)
			for _, value := range entries {
				if room, _ := value.(map[string]any)["room_id"].(string); room != "general" {
					t.Fatal("scope leaked in aggregate", method, key, room)
				}
			}
		}
	}
	result(t, bot.call(t, "message", map[string]any{"room_id": "general", "body": map[string]any{"text": "configured works"}}))
	// A human membership grant cannot expand operator scope, even for a private room.
	denied(t, human.call(t, "room_join", map[string]any{"room_id": private, "user_id": "hermes"}))
	bot.c.CloseNow()
	human.c.CloseNow()
	h.Close()
	s.Shutdown(context.Background())
	e = &enrolling{machine: e.machine, rooms: []string{"general", private, child}}
	s, h = open(e)
	bot = dial(t, h.URL)
	result(t, bot.call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
	for _, room := range e.rooms {
		result(t, bot.call(t, "history", map[string]any{"room_id": room}))
		result(t, bot.call(t, "message", map[string]any{"room_id": room, "body": map[string]any{"text": "explicit private/thread works"}}))
	}
	denied(t, bot.call(t, "history", map[string]any{"room_id": public}))
	bot.c.CloseNow()
	h.Close()
	s.Shutdown(context.Background())
	// The persisted exact scope remains valid on a second start with the same credential.
	_, h = open(&enrolling{machine: e.machine, rooms: e.rooms})
	bot = dial(t, h.URL)
	result(t, bot.call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
	result(t, bot.call(t, "history", map[string]any{"room_id": private}))
	denied(t, bot.call(t, "room_join", map[string]any{"room_id": public}))

}

// Thread metadata is broadcast to parent members upstream, even if they have
// never joined the child. Exact operator scope must also govern those deliveries.
func TestMachineRoomScopeLiveMetadata(t *testing.T) {
	e := &enrolling{machine: rand.Text() + rand.Text()}
	_, h, _ := enrollmentServer(t, func(c *apron.Config) { c.Extensions = []apron.Extension{e} })
	invite, err := e.policy.Issue(time.Minute, false)
	if err != nil {
		t.Fatal(err)
	}
	human := dial(t, h.URL)
	a := authn(t)
	o := begin(t, human, "register", invite)
	result(t, finish(t, human, "register", o, a.registration(t, o, origin, "localhost", 0x45)))
	bot := dial(t, h.URL)
	result(t, bot.call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
	child := result(t, human.call(t, "room_set", map[string]any{"parent_room_id": "general", "title": "Out of scope thread metadata"}))["room_id"]
	result(t, human.call(t, "room_set", map[string]any{"room_id": child, "title": "Out of scope update"}))
	if err = bot.c.Write(bot.ctx, websocket.MessageText, []byte(`{"id":"scope-barrier","method":"room_list","params":{"filter":"joined"}}`)); err != nil {
		t.Fatal(err)
	}
	for {
		frame := bot.read(t)
		if frame["id"] == "scope-barrier" {
			break
		}
		if frame["method"] == "room_update" {
			params := frame["params"].(map[string]any)
			for _, key := range []string{"joined", "updated", "left"} {
				records, _ := params[key].([]any)
				for _, value := range records {
					if value.(map[string]any)["room_id"] == child {
						t.Fatal("unconfigured child metadata broadcast to scoped parent member")
					}
				}
			}
		}
	}
}

func TestMachineUploadRechecksTargetMembership(t *testing.T) {
	for _, stage := range []string{"before-start", "during-body"} {
		t.Run(stage, func(t *testing.T) {
			e := &enrolling{machine: rand.Text() + rand.Text()}
			_, h, _ := enrollmentServer(t, func(c *apron.Config) { c.Extensions = []apron.Extension{e} })
			bot := dial(t, h.URL)
			result(t, bot.call(t, "auth", map[string]any{"scheme": "token", "token": e.machine}))
			receipt := result(t, bot.call(t, "message", map[string]any{"room_id": "general", "body": map[string]any{"text": "upload fixture", "embeds": []any{map[string]any{"kind": "upload"}}}}))
			capability := receipt["embeds"].([]any)[0].(map[string]any)["write_url"].(string)
			client := &http.Client{Timeout: 5 * time.Second}
			var response *http.Response
			var err error
			if stage == "before-start" {
				result(t, bot.call(t, "room_leave", map[string]any{"room_id": "general"}))
				request, _ := http.NewRequest(http.MethodPut, capability, strings.NewReader("fixture"))
				response, err = client.Do(request)
			} else {
				reader, writer := io.Pipe()
				defer reader.Close()
				defer writer.Close()
				started := make(chan struct{})
				trace := &httptrace.ClientTrace{Got100Continue: func() { close(started) }}
				request, _ := http.NewRequestWithContext(httptrace.WithClientTrace(context.Background(), trace), http.MethodPut, capability, reader)
				request.Header.Set("Expect", "100-continue")
				type outcome struct {
					response *http.Response
					err      error
				}
				finished := make(chan outcome, 1)
				go func() { r, err := client.Do(request); finished <- outcome{r, err} }()
				select {
				case <-started:
				case <-time.After(3 * time.Second):
					t.Fatal("upload did not enter real body receive")
				}
				result(t, bot.call(t, "room_leave", map[string]any{"room_id": "general"}))
				if _, err = writer.Write([]byte("fixture")); err != nil {
					t.Fatal("test body write failed")
				}
				writer.Close()
				got := <-finished
				response, err = got.response, got.err
			}
			if err != nil {
				t.Fatal("test upload request failed")
			}
			response.Body.Close()
			if response.StatusCode != http.StatusGone {
				t.Fatal("machine upload bypassed target membership", response.StatusCode)
			}
			result(t, bot.call(t, "room_join", map[string]any{"room_id": "general"}))
			history := result(t, bot.call(t, "history", map[string]any{"room_id": "general"}))
			for _, v := range history["messages"].([]any) {
				m := v.(map[string]any)
				if m["message_id"] == receipt["message_id"] {
					embeds, _ := m["body"].(map[string]any)["embeds"].([]any)
					for _, v := range embeds {
						if v.(map[string]any)["url"] != nil {
							t.Fatal("refused upload published a read capability")
						}
					}
				}
			}
		})
	}
}
