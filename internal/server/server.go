package server

import "github.com/apron-chat/apron-server-go/apron"

type Closed struct{ Allowlist *apron.Allowlist }

func (*Closed) Name() string                    { return "closed" }
func (p *Closed) Init(r *apron.Registrar) error { p.Allowlist = r.RestrictSignIn(); return nil }

func SecureConfig() apron.Config {
	c := apron.DefaultConfig()
	c.DisableGuests = true
	c.DisablePush = true
	c.TerminalViewerURL = ""
	c.Extensions = []apron.Extension{&Closed{}}
	return c
}
