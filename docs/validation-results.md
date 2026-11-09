# Executed validation

Implementation evidence, not deployment approval. Network/device/operator gates remain NOT RUN.

## TDD ledger

1. Closed admission: `go test ./internal/server -run TestFreshServerClosed -v`
   first reached the real pinned upstream server and failed: `fresh server offers forbidden scheme guest`.
   (An earlier setup attempt lacked dependency sums; another had an origin fixture mismatch. Neither counts as RED.)
   GREEN after enabling the supported empty `RestrictSignIn` allowlist, disabling guests and push:
   focused test PASS; `go test ./...` PASS (one test). Unauthenticated room/history/status/message requests denied.

Further evidence is appended as slices execute. No hypothetical result is a pass.

2. Invitation verifier: `go test ./internal/server -run TestInvitationVerifierOnly -v`
   (with the patched workspace) RED: invitation lacked 256 random bits. GREEN after 32-byte randomness,
   SHA-256 verifier-only durable storage. Initial rand.Text variant had only 130 bits and also failed.
3. Invited WebAuthn: `go test ./internal/server -run TestInvitedRegistration -v`
   RED from real upstream: `Sign in as a guest before adding a passkey`.
   GREEN after invitation-bound preauth registration, upstream WebAuthn verification, and a single
   durable account+policy transaction. Earlier numeric RPC ID fixture timed out and was corrected;
   it is not counted as the behavioral RED.
4. Pending invitation revocation: focused `TestRevocationClosesPendingInvitation` RED accepted
   a revoked invite; GREEN after durable deletion and rechecking policy at finish.
5. Account revocation: focused `TestAccountRevocationDisconnectsAndRejectsResume` RED resumed
   a revoked account; GREEN after removing immutable-ID admission and upstream sign-out of all
   connections, sessions, devices and push registrations.
6. Machine identity: focused `TestSeparateMachineIdentityRevocable` RED: session expired for
   runtime machine credential; GREEN: two native WS connections share a separate non-admin bot,
   and revocation rejects its credential.

`go test -race ./internal/server -run 'TestConcurrent|TestForged' -count=3 -v`: PASS.
`go test -race ./internal/server -v`: PASS, 10 top-level tests. Real sockets, real WebAuthn verifier,
SQLite restart, one winning concurrent redemption, wrong origin/RP/UV, challenge/invite replay,
revocation and one injected enrollment Apply failure. Failure disconnects before success; restart
has zero half-created users and the unused invitation can enroll. This is not a power-loss test at
all SQLite internals, nor browser/device evidence. Software authenticators sign real test challenges.
`tools/go test ./...`: PASS using a fresh materialization of the pinned patch, Go 1.27.0.

7. Safe listener settings: `tools/go test ./internal/server -run TestRejectUnsafeProductionSettings -v`
   RED accepted `:8080`; GREEN rejects wildcard IPv4/IPv6, insecure production origin,
   wildcard origin, URL credentials/path, and non-ephemeral test listeners.
   `tools/go test ./...` PASS; `tools/go build ./cmd/apron-home` PASS.
8. Browser: `PLAYWRIGHT_NODEJS_PATH="$(command -v node)" LD_LIBRARY_PATH="$(nix eval --raw nixpkgs#stdenv.cc.cc.lib.outPath)/lib" HERMES_APRON_BINARY=<scratch-binary> <scratch-venv>/bin/pytest tests/test_browser.py -q`
   PASS (1): installed Chromium, real virtual CTAP2 authenticator with resident keys and user
   verification; local enrollment UI creates an account, a separate native WebAuthn login succeeds,
   invitation input clears, captured HTTP requests stay on origin. No real passkey/device access.
   First attempts could not import greenlet's libstdc++ and could not launch Playwright's generic
   bundled Node on NixOS. These setup failures are not behavioral RED evidence.

Frontend build: pinned server submodule commit 95a6314e2629f0965dd61fa688f7eb1b4abbd26c,
`npm ci --ignore-scripts && npm run prepare && npm run build` PASS.
Initial `npm audit --json`: 12 findings (5 low, 2 moderate, 4 high, 1 critical), including DOMPurify
and Markdown-it. A compatible lockfile update removes moderate/high/critical findings; the
patched runtime `npm audit --omit=dev --audit-level=moderate` reports zero vulnerabilities.
Remaining dev-only low findings are still tracked; full frontend test results pending.
