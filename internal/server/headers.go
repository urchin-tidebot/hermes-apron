package server

import (
	"net/http"
	"strings"
)

// LocalHeaders confines the self-hosted client to this origin. External links may
// still be opened intentionally by a human; embedded content cannot fetch them.
func LocalHeaders(next http.Handler, origin string) http.Handler {
	ws := strings.Replace(strings.Replace(origin, "https://", "wss://", 1), "http://", "ws://", 1)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Security-Policy", "default-src 'self'; connect-src 'self' "+ws+"; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'; worker-src 'self' blob:; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		next.ServeHTTP(w, r)
	})
}
