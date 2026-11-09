package server

import (
	"context"
	"encoding/json"
	"errors"
	"github.com/apron-chat/apron-server-go/apron"
	"io"
	"net"
	"net/http"
	"os"
	"time"
)

func (p *Closed) startControl(h *apron.Host) error {
	if info, err := os.Lstat(p.ControlPath); err == nil {
		if info.Mode()&os.ModeSocket == 0 {
			return errors.New("control path is not a socket")
		}
		if err = os.Remove(p.ControlPath); err != nil {
			return err
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	l, err := net.Listen("unix", p.ControlPath)
	if err != nil {
		return errors.New("cannot bind operator socket")
	}
	if err = os.Chmod(p.ControlPath, 0600); err != nil {
		l.Close()
		return err
	}
	mux := http.NewServeMux()
	mux.HandleFunc("POST /invite", func(w http.ResponseWriter, r *http.Request) {
		var v struct {
			TTL   int  `json:"ttl_seconds"`
			Owner bool `json:"owner"`
		}
		if !decodeControl(w, r, &v) {
			return
		}
		token, err := p.Enrollment.Issue(time.Duration(v.TTL)*time.Second, v.Owner)
		if err != nil {
			http.Error(w, "invitation unavailable", 409)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"token": token})
	})
	mux.HandleFunc("POST /revoke", func(w http.ResponseWriter, r *http.Request) {
		var v struct {
			Account  string `json:"account"`
			Verifier string `json:"verifier"`
		}
		if !decodeControl(w, r, &v) {
			return
		}
		var err error
		if (v.Account == "") == (v.Verifier == "") {
			http.Error(w, "choose one revocation target", 400)
			return
		}
		if v.Account != "" {
			err = p.Enrollment.RevokeAccount(v.Account)
		} else {
			err = p.Enrollment.RevokeInvitation(v.Verifier)
		}
		if err != nil {
			http.Error(w, "revocation failed", 503)
			return
		}
		w.WriteHeader(204)
	})
	srv := &http.Server{Handler: mux, ReadHeaderTimeout: 3 * time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 5 * time.Second, IdleTimeout: 5 * time.Second, MaxHeaderBytes: 4096}
	h.Go(func(ctx context.Context) {
		go func() { <-ctx.Done(); _ = srv.Close() }()
		_ = srv.Serve(l)
		_ = l.Close()
		_ = os.Remove(p.ControlPath)
	})
	return nil
}
func decodeControl(w http.ResponseWriter, r *http.Request, v any) bool {
	r.Body = http.MaxBytesReader(w, r.Body, 2048)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	if d.Decode(v) != nil {
		http.Error(w, "invalid operator request", 400)
		return false
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		http.Error(w, "invalid operator request", 400)
		return false
	}
	return true
}
