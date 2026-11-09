package server

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"syscall"
)

func PrivateDir(path string) error {
	if path == "" {
		return errors.New("private directory required")
	}
	if err := os.MkdirAll(path, 0700); err != nil {
		return errors.New("cannot create private directory")
	}
	info, err := os.Lstat(path)
	if err != nil || !info.IsDir() || info.Mode().Perm()&0077 != 0 {
		return errors.New("state directory must be private (0700) and not a symlink")
	}
	if st, ok := info.Sys().(*syscall.Stat_t); !ok || st.Uid != uint32(os.Geteuid()) {
		return errors.New("state directory must belong to this user")
	}
	return nil
}
func ReadSecret(path string) (string, error) {
	fd, err := syscall.Open(path, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC|syscall.O_NONBLOCK, 0)
	if err != nil {
		return "", errors.New("cannot open credential file")
	}
	f := os.NewFile(uintptr(fd), "credential")
	defer f.Close()
	info, err := f.Stat()
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 || info.Size() > 1024 {
		return "", errors.New("credential file must be private, regular and bounded")
	}
	if st, ok := info.Sys().(*syscall.Stat_t); !ok || st.Uid != uint32(os.Geteuid()) {
		return "", errors.New("credential file must belong to this user")
	}
	b, err := io.ReadAll(io.LimitReader(f, 1025))
	if err != nil {
		return "", errors.New("cannot read credential file")
	}
	token := strings.TrimSpace(string(b))
	if len(token) < 43 || strings.ContainsAny(token, "\r\n\x00 ") {
		return "", errors.New("invalid runtime credential")
	}
	return token, nil
}
func LockState(path string) (func(), error) {
	if err := PrivateDir(path); err != nil {
		return nil, err
	}
	fd, err := syscall.Open(filepath.Join(path, "server.lock"), syscall.O_CREAT|syscall.O_RDWR|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0600)
	if err != nil {
		return nil, errors.New("cannot open state lock")
	}
	if err = syscall.Flock(fd, syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		syscall.Close(fd)
		return nil, errors.New("state directory already in use")
	}
	return func() { syscall.Flock(fd, syscall.LOCK_UN); syscall.Close(fd) }, nil
}
