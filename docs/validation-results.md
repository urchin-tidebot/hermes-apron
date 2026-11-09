# Executed validation

Implementation evidence, not deployment approval. Network/device/operator gates remain NOT RUN.

## TDD ledger

1. Closed admission: `go test ./internal/server -run TestFreshServerClosed -v`
   first reached the real pinned upstream server and failed: `fresh server offers forbidden scheme guest`.
   (An earlier setup attempt lacked dependency sums; another had an origin fixture mismatch. Neither counts as RED.)
   GREEN after enabling the supported empty `RestrictSignIn` allowlist, disabling guests and push:
   focused test PASS; `go test ./...` PASS (one test). Unauthenticated room/history/status/message requests denied.

Further evidence is appended as slices execute. No hypothetical result is a pass.
