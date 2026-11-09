package server

import (
	"path/filepath"
	"strings"
	"syscall"
	"testing"
)

func TestLongControlPathDiagnostic(t *testing.T) {
	for name, component := range map[string]string{"ascii": strings.Repeat("x", 108), "utf8": strings.Repeat("界", 36)} {
		t.Run(name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), component)
			if len(path) < len(syscall.RawSockaddrUnix{}.Path) {
				t.Fatal("fixture did not exceed socket path capacity")
			}
			closed := &Closed{ControlPath: path}
			err := closed.startControl(nil)
			if err == nil || !strings.Contains(err.Error(), "operator socket path is too long") || !strings.Contains(err.Error(), "shorter private state directory") || strings.Contains(err.Error(), path) {
				t.Fatalf("missing safe long-path diagnostic: %v", err)
			}
		})
	}
}
