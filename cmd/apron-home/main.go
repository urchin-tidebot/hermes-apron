// apron-home has a deliberately smaller configuration surface than aprond.
package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/apron-chat/apron-server-go/apron"
	"github.com/apron-chat/apron-server-go/aproncmd"
	"github.com/apron-chat/apron-server-go/store"
	"github.com/urchin-tidebot/hermes-apron/internal/server"
	"golang.org/x/net/netutil"
	"io"
	"log/slog"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
func run(args []string) error {
	if len(args) == 0 {
		return errors.New("use serve, invite, revoke-account, revoke-invite, or machine-secret")
	}
	f := flag.NewFlagSet(args[0], flag.ContinueOnError)
	f.SetOutput(io.Discard)
	state := f.String("state-dir", "", "private runtime state directory")
	output := f.String("output", "", "create a private output file (must not exist)")
	stdout := f.Bool("stdout", false, "intentionally print invitation once")
	ttl := f.Int("ttl-seconds", 600, "invitation TTL, max 900")
	owner := f.Bool("owner", false, "explicitly grant owner/admin to the enrolled human")
	id := f.String("id", "", "immutable account ID or invitation verifier")
	settings := server.Settings{}
	f.StringVar(&settings.Listen, "listen", "127.0.0.1:8080", "loopback backend")
	f.StringVar(&settings.PublicURL, "public-url", "", "exact public HTTPS origin")
	f.StringVar(&settings.FrontendDir, "frontend-dir", "", "pinned built Apron frontend")
	f.StringVar(&settings.MachineFile, "machine-file", "", "private runtime bot credential file")
	f.BoolVar(&settings.TestLoopback, "test-loopback", false, "HTTP tests only; requires --listen 127.0.0.1:0")
	rooms := f.String("rooms", "", "explicit comma-separated machine room IDs")
	if err := f.Parse(args[1:]); err != nil || f.NArg() != 0 {
		return errors.New("invalid arguments")
	}
	settings.StateDir = *state
	for _, room := range strings.Split(*rooms, ",") {
		if room != "" {
			settings.Rooms = append(settings.Rooms, room)
		}
	}
	switch args[0] {
	case "serve":
		return serve(settings)
	case "machine-secret":
		if *output == "" || *stdout {
			return errors.New("machine-secret requires --output")
		}
		var secret [32]byte
		if _, err := rand.Read(secret[:]); err != nil {
			return err
		}
		return writeOnce(*output, base64.RawURLEncoding.EncodeToString(secret[:])+"\n")
	case "invite":
		if (*output == "") == !*stdout {
			return errors.New("choose exactly one intentional delivery mode: --output or --stdout")
		}
		// Reserve the output before issuing, so an existing file never loses its invitation.
		var file *os.File
		var err error
		if *output != "" {
			file, err = os.OpenFile(*output, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
			if err != nil {
				return errors.New("cannot create invitation output")
			}
			defer file.Close()
		}
		raw, err := operator(*state, "invite", map[string]any{"ttl_seconds": *ttl, "owner": *owner})
		if err != nil {
			if file != nil {
				os.Remove(*output)
			}
			return err
		}
		var r struct {
			Token string `json:"token"`
		}
		if json.Unmarshal(raw, &r) != nil || r.Token == "" {
			return errors.New("invalid operator reply")
		}
		if file != nil {
			_, err = io.WriteString(file, r.Token+"\n")
			if err == nil {
				err = file.Sync()
			}
			return err
		}
		fmt.Println(r.Token)
		return nil
	case "revoke-account", "revoke-invite":
		if *id == "" {
			return errors.New("revocation requires --id")
		}
		v := map[string]string{}
		if args[0] == "revoke-account" {
			v["account"] = *id
		} else {
			v["verifier"] = *id
		}
		_, err := operator(*state, "revoke", v)
		return err
	default:
		return errors.New("unknown command")
	}
}
func writeOnce(path, text string) error {
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return errors.New("cannot create private output file")
	}
	defer f.Close()
	if _, err = f.WriteString(text); err != nil {
		return err
	}
	return f.Sync()
}
func operator(state, method string, v any) ([]byte, error) {
	if err := server.PrivateDir(state); err != nil {
		return nil, err
	}
	body, _ := json.Marshal(v)
	transport := &http.Transport{DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
		return (&net.Dialer{Timeout: 3 * time.Second}).DialContext(ctx, "unix", filepath.Join(state, "operator.sock"))
	}}
	defer transport.CloseIdleConnections()
	client := &http.Client{Transport: transport, Timeout: 5 * time.Second}
	r, err := client.Post("http://operator/"+method, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, errors.New("operator socket unavailable")
	}
	defer r.Body.Close()
	if r.StatusCode < 200 || r.StatusCode >= 300 {
		return nil, errors.New("operator request denied or persistence failed")
	}
	return io.ReadAll(io.LimitReader(r.Body, 2048))
}
func serve(settings server.Settings) error {
	if err := settings.Validate(); err != nil {
		return err
	}
	release, err := server.LockState(settings.StateDir)
	if err != nil {
		return err
	}
	defer release()
	uploads := filepath.Join(settings.StateDir, "uploads")
	if err = server.PrivateDir(uploads); err != nil {
		return err
	}
	// Only loopback is permitted. TLS and LAN ingress belong to an explicit proxy.
	listener, err := net.Listen("tcp", settings.Listen)
	if err != nil {
		return errors.New("cannot bind loopback listener")
	}
	defer listener.Close()
	if settings.TestLoopback {
		_, port, _ := net.SplitHostPort(listener.Addr().String())
		settings.PublicURL = "http://localhost:" + port
	}
	u, _ := url.Parse(settings.PublicURL)
	opts := aproncmd.Options{Addr: settings.Listen, PublicURL: settings.PublicURL, StaticDir: settings.FrontendDir, Origins: []string{settings.PublicURL}, DisableGuests: true, MaxConnections: 64, MessagesPerMinute: 60, MaxListedMembers: 1000, MaxPrivateRooms: 32}
	opts.WebAuthn.RPID = u.Hostname()
	opts.WebAuthn.Origins = []string{settings.PublicURL}
	opts.Push.Disable = true
	opts.Upload.Dir = uploads
	opts.Upload.MaxMB = 8
	opts.Upload.MaxMessageMB = 16
	opts.Upload.MaxStorageMB = 128
	opts.Live.MaxMinutes = 5
	opts.Live.MaxMB = 1
	opts.Live.TerminalKeepKB = 16
	opts.Live.AppendMaxKB = 64
	opts.Live.TerminalViewer = ""
	opts.Emoji.MaxKB = 256
	opts.Emoji.MaxStorageMB = 16
	cfg, err := aproncmd.ServerConfig(opts)
	if err != nil {
		return errors.New("invalid upstream configuration")
	}
	closed := &server.Closed{ControlPath: filepath.Join(settings.StateDir, "operator.sock"), Rooms: settings.Rooms}
	if settings.MachineFile != "" {
		closed.Machine, err = server.ReadSecret(settings.MachineFile)
		if err != nil {
			return err
		}
	}
	cfg.Extensions = []apron.Extension{closed}
	cfg.Store, err = store.OpenSQLite(filepath.Join(settings.StateDir, "server.db"))
	if err != nil {
		return errors.New("cannot open persistent state")
	}
	cfg.Logger = slog.New(slog.NewTextHandler(os.Stderr, nil))
	app, err := apron.Open(cfg)
	if err != nil {
		return errors.New("server initialization failed")
	}
	defer app.Shutdown(context.Background())
	srv := &http.Server{Handler: app, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 6 * time.Minute, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 8192}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	done := make(chan error, 1)
	go func() { done <- srv.Serve(netutil.LimitListener(listener, 128)) }()
	// Only the explicit loopback test harness gets a machine-readable ephemeral address.
	if settings.TestLoopback {
		json.NewEncoder(os.Stdout).Encode(map[string]string{"url": settings.PublicURL})
	}
	select {
	case <-ctx.Done():
	case <-done:
	}
	shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = srv.Shutdown(shutdown)
	return app.Shutdown(shutdown)
}
