package server

import (
	"fmt"
	"github.com/apron-chat/apron-server-go/apron"
	"net/http"
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
		_, err := r.Bot("hermes", apron.BotOptions{Name: "Hermes"})
		if err != nil {
			return err
		}
		if err = p.Enrollment.BindMachine("hermes", p.Machine, 7*24*time.Hour, p.Rooms); err != nil {
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
