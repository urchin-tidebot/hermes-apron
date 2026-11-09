package server

import "testing"

func TestRejectUnsafeProductionSettings(t *testing.T) {
	for _, s := range []Settings{
		{Listen: ":8080", PublicURL: "https://chat.example.test"},
		{Listen: "[::]:8080", PublicURL: "https://chat.example.test"},
		{Listen: "127.0.0.1:8080", PublicURL: "http://chat.example.test"},
		{Listen: "127.0.0.1:8080", PublicURL: "https://*.example.test"},
		{Listen: "127.0.0.1:8080", PublicURL: "https://chat.example.test/path"},
		{Listen: "127.0.0.1:8080", PublicURL: "https://user:secret@chat.example.test"},
		{Listen: "0.0.0.0:0", TestLoopback: true},
		{Listen: "127.0.0.1:8080", TestLoopback: true},
	} {
		if s.Validate() == nil {
			t.Fatalf("accepted unsafe settings: listen=%s", s.Listen)
		}
	}
}
