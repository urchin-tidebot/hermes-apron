package server

import (
	"errors"
	"net"
	"net/url"
	"regexp"
	"strings"
)

type Settings struct {
	Listen, PublicURL, StateDir, FrontendDir, MachineFile string
	TestLoopback                                          bool
	Rooms                                                 []string
}

var hostname = regexp.MustCompile(`^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$`)

func (s Settings) Validate() error {
	host, port, err := net.SplitHostPort(s.Listen)
	if err != nil || net.ParseIP(host) == nil || !net.ParseIP(host).IsLoopback() {
		return errors.New("listen must be an explicit loopback IP and port; use a separately restricted TLS proxy for LAN")
	}
	if s.TestLoopback {
		if port != "0" || s.PublicURL != "" {
			return errors.New("test mode requires ephemeral loopback and no production public URL")
		}
		return nil
	}
	u, err := url.Parse(s.PublicURL)
	if err != nil || u.Scheme != "https" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || u.Path != "" || u.Opaque != "" || !hostname.MatchString(u.Hostname()) || strings.Contains(s.PublicURL, "*") {
		return errors.New("production requires an exact HTTPS origin and narrow DNS hostname")
	}
	if s.StateDir == "" || s.FrontendDir == "" {
		return errors.New("production requires private state and a locally built frontend")
	}
	return nil
}
