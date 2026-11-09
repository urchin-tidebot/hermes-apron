package server

import (
	"path/filepath"
	"syscall"
	"testing"
	"time"
)

func TestCredentialFIFOIsRejectedWithoutBlocking(t *testing.T) {
	path := filepath.Join(t.TempDir(), "credential-fifo")
	if err := syscall.Mkfifo(path, 0600); err != nil {
		t.Fatal(err)
	}
	done := make(chan error, 1)
	go func() { _, err := ReadSecret(path); done <- err }()
	select {
	case err := <-done:
		if err == nil {
			t.Fatal("non-regular credential accepted")
		}
	case <-time.After(200 * time.Millisecond):
		t.Fatal("credential special file blocked startup")
	}
}
