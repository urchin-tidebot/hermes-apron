package server

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/apron-chat/apron-server-go/apron"
	"net/http"
	"slices"
	"time"
)

type Closed struct {
	Allowlist   *apron.Allowlist
	Enrollment  *apron.Enrollment
	Machine     string
	Rooms       []string
	ControlPath string
}

func (*Closed) Name() string { return "closed" }
func (p *Closed) Init(r *apron.Registrar) error {
	var err error
	p.Enrollment, err = r.ClosedEnrollment()
	if err != nil {
		return err
	}
	if p.Machine != "" {
		if len(p.Rooms) == 0 {
			return fmt.Errorf("machine identity needs explicit rooms")
		}
		bot, err := r.Bot("hermes", apron.BotOptions{Name: "Hermes"})
		if err != nil {
			return err
		}
		raw, err := bot.Call(context.Background(), "room_list", map[string]any{"filter": "joined"})
		if err != nil {
			return err
		}
		var joined struct {
			Joined []struct {
				ID string `json:"room_id"`
			}
		}
		if err = json.Unmarshal(raw, &joined); err != nil {
			return err
		}
		for _, room := range joined.Joined {
			if !slices.Contains(p.Rooms, room.ID) {
				if _, err = bot.Call(context.Background(), "room_leave", map[string]any{"room_id": room.ID}); err != nil {
					return err
				}
			}
		}
		for _, room := range p.Rooms {
			if err = bot.Join(context.Background(), room); err != nil {
				return err
			}
		}
		if err = p.Enrollment.BindMachine("hermes", p.Machine, 7*24*time.Hour); err != nil {
			return err
		}
	}
	r.Handle("/enroll/", http.HandlerFunc(enrollmentPage))
	if p.ControlPath != "" {
		return p.startControl(r.Host)
	}
	return nil
}

func SecureConfig() apron.Config {
	c := apron.DefaultConfig()
	c.DisableGuests = true
	c.DisablePush = true
	c.TerminalViewerURL = ""
	c.Extensions = []apron.Extension{&Closed{}}
	return c
}
