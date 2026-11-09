# Isolated upstream patch

`closed-enrollment.patch` applies only to server commit
`cefba0193cf5cf8407dfb47c0970b9a26e6c1b8c` (MIT). No server tree is vendored or fork published.
`tools/go` materializes it in TMPDIR and uses a Go workspace; ordinary `go test` without that
workspace intentionally cannot compile consumers of the added API.

Upstream `Registrar.RestrictSignIn`, bots, WebAuthn verification and validation stay authoritative.
Its API cannot register a passkey without a guest, nor atomically couple two separate databases.
The added `Registrar.ClosedEnrollment` stores invitation verifiers and immutable account admission
in the SAME upstream store transaction as the verified new credential/account. Registration
creates no guest and no account before successful verification. The invitation is checked again
under the server lock. No user-selected display name or user ID grants admission or ownership.

For this patch all store writes serialize synchronously under the server lock. A failed write
stops further writes and client requests, closes connections, and requires restart. Enrollment
success is sent only after its account/policy commit; session creation also waits for persistence.
A storage error does not roll back mutated memory: it makes that process unusable. Restart rebuilds
only committed state. This deliberately favors consistency over availability and needs independent
review. Do not remove the persistence fence for performance without redesigning the transaction.

Runtime machine credentials authenticate extension-owned bots through native token auth, never a
human session. Only hashes persist. Rotation/revocation closes existing sessions. Old revoked
credentials stay revoked on a restart with the same runtime file. Device token creation is disabled
because upstream tokens have no expiry. Human session resume retains its original absolute expiry.

This remains a project patch, not an upstream-supported release or an audited security boundary.

Additional review fixes keep signup metadata closed, stop HTTP after persistence failure,
forbid machine accounts adding human credentials, and require bot membership at the server's
message commit boundary. SQLite uses synchronous FULL (with an actual connection pragma test).
Human token expiry limits new resumption; active sockets still require explicit revocation/closure.
The workspace pins current dependency security fixes above the original module minimums; see
[provenance](../docs/provenance.md). These controls have regression tests but remain unaudited.

Machine credentials persist an exact operator room-ID scope. The shared room visibility rule
checks that scope (including explicit thread ancestors), and reads, posts, edits, commands,
activity and embed creation use it. Machine room creation is denied; adding a machine as a
member cannot expand its scope. Binding reconciles membership under the same server lock and
can admit configured existing private rooms. Provision rooms as a human, then restart with
those room and parent IDs in `--rooms`; no bot-side provisioning or inherited thread scope.
Existing policy without room IDs grants no visibility until explicitly bound with operator scope.

Machine expiry has one timer per identity. Binding/restoring schedules the persisted deadline;
rotation, revocation and shutdown stop/remove timers. Generation checks make already-runnable
old callbacks harmless. Dispatch checks the real clock as well, and room/message commit checks
prevent a frame delayed in an extension filter from writing after expiry. Expiry signs out every
connection of the machine identity. This does not change the documented independent bearer
lifetime of HTTP media capabilities already issued.
