# Executed validation

Implementation evidence, not deployment approval. Network/device/operator gates remain NOT RUN.

## Final remediation validation — 2026-11-09

Authoritative totals for this worktree; counts in the numbered TDD chronology below are historical,
not current aggregate counts. The requirements and release gates remain unchanged.

| Command (inside pinned `nix develop`, with private scratch `TMPDIR`) | Actual result |
|---|---|
| `make check` | PASS after the documented human-delta regression was corrected. Includes wrapper/upstream races, full Python/browser suite, lint, binary build, content audit and dependency audits |
| `tools/go test -race ./...` | PASS: **19 top-level wrapper Go tests**; command package has no test files. Final rerun includes restored-policy-without-rebind, implicit default target and known message/embed-ID assertions |
| `tools/test -q` | PASS: **113 Python tests**, including actual pinned Hermes, real Go server, Chromium virtual WebAuthn and pinned frontend browser E2E; no skips reported |
| `tools/upstream-test` | PASS under race detection: real patched `apron`, `aproncmd`, `store`, with pinned protocol fixtures initialized |
| `tools/frontend --test` | PASS: **200 files / 1,691 tests**; Svelte 0 errors / 0 warnings; runtime npm audit 0 vulnerabilities; local static build PASS. Five low development-only findings remain |
| `nix flake check --no-update-lock-file` | PASS on x86_64-linux; aarch64-linux omitted as incompatible, not counted as a pass |
| `tools/go vet ./...`, gofmt, Ruff check/format | PASS; **24 Python source/test/tool files** formatted |
| `tools/build` | PASS, binary plus notices for **28 runtime Go modules** and Go standard library in scratch |
| `tools/go run golang.org/x/vuln/cmd/govulncheck@v1.9.0 ./...` | PASS: no vulnerabilities found with pinned Go 1.27.3 |
| `python3 tools/dependency_audit.py` | PASS: **40 locked public Python registry packages**, zero OSV findings |
| `python3 tools/audit.py` and `gitleaks dir/git --redact` (`b899490..HEAD`) | PASS on source/added history; code snapshot `d47a451`: **71 source files / 13 added commits**. Final test/docs working tree and committed history rescanned before handoff; raw logs stay in scratch |
| `python3 tools/public_run.py uv --no-config build --out-dir <scratch>` | PASS: wheel and sdist. Archive name/content audit PASS: **14 wheel files / 25 sdist files**. uv's separate `.gitignore` helper was inspected and excluded from archive counts |

The final code-validation snapshot is `d47a451`; subsequent changes strengthen wire assertions and
update evidence/status only. Frontend/build/dependency pins did not change. The public v10 protocol
was fetched again and its SHA-256 still matches the provenance entry. Test state, generated
credentials, locks, browser authenticators, logs and artifacts stayed in disposable scratch.
No production secrets/configuration were read. No deployment, gateway/Telegram/firewall/root/
Home Manager changes, push, PR, fork, history rewrite or protected instruction edits occurred.

Parent fix review and publication approval, safe affirmative consent, supported credential removal,
full license/security review, resource/crash/recovery coverage, and real LAN/TLS/device/IPv6 acceptance
remain release blockers. Green tests do not clear them. Already-issued read capability URLs and
previously shared bytes remain bearer/copy risks; machine room write targets are now rechecked.

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

9. Native Python transport: focused `tests/test_transport.py::test_real_greeting_and_machine_authentication`
   RED: native machine auth never completed; GREEN: v10 greeting, token authentication, exact bot role.
10. Hermes authority: `test_only_allowed_structured_mentions_reach_hermes` RED: allowed structured
    mention dropped; GREEN: configured immutable actor IDs and rooms, structured mentions, no echo,
    bots, tombstones, edits, display-name mentions or administrative slash-command interception.
    Setup first demonstrated that `Platform('apron')` needs real registry registration; tests now use
    the pinned real `PluginManager`, `PluginContext`, registry and `BasePlatformAdapter`.
11. `test_native_send_receipt_from_real_adapter` RED: adapter did not connect; GREEN: Markdown send
    confirmed by real history readback, unauthorized destination refused.
12. `test_real_human_invocation_with_hermes_handler` RED timed out without a receive worker;
    GREEN: Chromium-enrolled human reaches a real BasePlatformAdapter message handler, no model calls.
13. `test_offline_history_recovers_once_after_new_adapter` RED timed out on missing history recovery;
    GREEN with bounded high-water recovery, private SQLite checkpoints and dispatch reservations.
    An early cancelled receive worker leaked queue waiters; replacing it with cancellable bounded
    waits removed the teardown exception. Reservations favor avoiding repeated tool execution:
    process death after reserve can lose a turn. This is NOT exactly-once side-effect execution.
14. `test_native_append_finishes_same_message` RED: edit Not supported;
    GREEN: real append PUT, full-text revisions, completion and history show one message ID/final body.
15. `test_native_upload_rejects_traversal_and_reads_back` RED: inherited Hermes fallback posted no
    embed (and logged a path); GREEN: native upload, safe basename, flat private export directory,
    traversal/symlink rejection. No HTTP client logs capability URLs.
16. `test_standalone_delivery_coexists_with_consumer` RED: unavailable;
    GREEN: separate native connection does not take the consumer lock. Separate-process CLI delivery
    is also tested with receipt readback and the live consumer still usable.
17. `test_typing_activity_is_native` RED timed out; GREEN native activity start and clear.
18. `test_opt_in_terminal_summary_scrubs_runtime_credential` RED refused approved summary;
    GREEN: explicit opt-in + per-call approval, bounded reviewed summary, ANSI stripping and known
    runtime credential/capability URL scrubbing. No arbitrary tool-output hook or shell execution.
19. `test_reconnect_replaces_transport_with_bounded_retry` RED timed out;
    GREEN bounded retries/backoff, replacement transport, history recovery, send after reconnect.
20. Security review regressions: scalar mentions RED incorrectly authorized; GREEN strict list shape.
    Corrupt inbox RED raised DatabaseError and retained its lock; GREEN fails closed and releases it.
    Unsupported open-ended clarification RED left a real Hermes waiter accepting arbitrary next text;
    GREEN cancels that exact session/request. Other pending sessions remain untouched.
21. Go security review: `TestMachineCannotAddHumanPasskey` RED offered registration to the bot;
    GREEN denies human auth schemes for bots, preventing a second persistent machine auth path.
    `TestEnrollmentFailureAtomicAcrossRestart` extended with HTTP: RED served after store fault;
    GREEN returns 503 as well as closing WS. `TestFreshServerClosed` extended: RED advertised open
    signup; GREEN advertises no open signup while retaining passkey login.
22. Frontend local-mode test: RED copied a link through link.apron.chat; GREEN same-origin share links,
    default WebSocket origin and no external terminal viewer in `VITE_LOCAL_ONLY=1` builds.
    Four focused upstream frontend files: 51 tests PASS. Upstream defaults are unchanged outside local mode.

`tools/test -q`: PASS, 24 tests (before the last added Go-only metadata regression), using pinned public
Hermes source and a sanitized test environment. Includes real server/browser/plugin exchanges plus
adversarial RPC ordering/timeouts/cancellation and redacted denied/retry errors. Synthetic protocol
peers supplement, rather than replace, the real-server tests.

Frontend checks after fetching its pinned protocol submodule: `npm run check` PASS (0 diagnostics).
First full frontend run: 1689 PASS, 1 timeout at default 5s. Rerun with explicit 20s timeout:
`npm test -- --testTimeout=20000`: 1690 PASS. Canvas warning is from jsdom and is not a claimed canvas test.
Final local-mode build and full-suite results will be recorded below.

`tools/frontend --test` with the final local frontend patch: PASS, 200 files / 1691 tests;
Svelte check 0 diagnostics; runtime audit 0 vulnerabilities; static build PASS. Development-only
low-severity SvelteKit/cookie/deepmerge findings remain (5); no claim they were fixed.
`tools/upstream-test`: PASS under race detection for patched real `apron`, `aproncmd`, `store`,
with the pinned protocol fixtures initialized. No unit-only substitution for the server.
`tools/go test -race ./...`: PASS after the bot-passkey, fault-HTTP and signup metadata fixes.
`tools/test tests/test_adapter.py -k two_private -q`: PASS: two private rooms and two child threads,
concurrent real Hermes handlers, native sends/replies and per-room history readback stay isolated.
`tools/test tests/test_browser.py -k pinned_frontend -q`: PASS: actual pinned self-hosted Svelte client,
virtual passkey login and native chat render/send; HTTP and WebSocket requests stay on the local origin.
An initial selector guessed `connect-submit`; inspection found `passkey-login` and `message-input`.
That fixture failure is not a production-behavior RED.

23. `test_same_credential_cannot_start_second_consumer_profile`: RED allowed two consumers with
    different state directories; GREEN uses the real Hermes scoped credential reservation plus
    same-process exclusion. Standalone send-only delivery remains allowed. Test lock rendezvous is
    explicitly redirected to private scratch; the installed gateway's lock/state is not accessed.
24. `TestClosedWrapperRequiresDurableSQLiteCommits` in the pinned store: RED reported synchronous=1
    (NORMAL); GREEN after the documented FULL override reports 2. This tests the actual connection
    pragma, not a string match; it does not simulate hardware power loss.

Additional regressions cover core-only capability fallback (no fabricated optional RPCs), canary
absence from captured server logs/SQLite/generated binary, private credential/socket modes,
real plugin-loader import and profile-scoped passive config validation.

25. Cross-room edit regression: `test_edit_is_bound_to_original_room` RED moved a message to another
    configured conversation; GREEN binds editable message IDs to their original room (bounded map).
    `TestMachineMustBeJoinedToPost` RED allowed implicit post/rejoin after leave; GREEN checks actual
    bot membership under the upstream commit lock, without changing ordinary upstream guest behavior.
26. Dependency audit: initial `tools/go run golang.org/x/vuln/cmd/govulncheck@v1.9.0 ./...` under
    Go 1.27.0 reported 13 reachable standard-library advisories, plus unused module findings.
    Compiler pin changed to Go 1.27.3; x/net updated to v0.62.0 and x/crypto to the verified official
    fix pseudo-version v0.58.1-0.20261009181718-2f1f834330b2. The requested stable v0.59.0 crypto
    did not exist and was not used. Final verbose audit: no vulnerabilities at symbol/package/module
    levels. This is an advisory database result, not independent security review.
    OSV querybatch for the 40 registry packages in final uv.lock: 40 queried, zero findings (2026-11-09).
    Removed an unused HTTP client dependency; native capability writes use bounded stdlib I/O without URL logging.

`nix shell nixpkgs#gitleaks --command gitleaks dir --redact --no-banner --exit-code 1 .`: PASS.
`nix shell nixpkgs#gitleaks --command gitleaks git --redact --no-banner --log-opts='b899490..HEAD' .`: PASS
at the time (4 implementation commits); final added history is rescanned below. No secret-content output
or raw Codex/test transcripts are committed. The custom audit checks private addresses/state paths too.

27. `TestCredentialFIFOIsRejectedWithoutBlocking` RED blocked startup on a non-regular credential
    file; GREEN after no-follow/nonblocking open, preserving the regular/private/owned file checks.
28. Proxy example: `nix shell nixpkgs#caddy --command caddy adapt --config examples/lan-proxy.Caddyfile --adapter caddyfile`
    PASS syntax adaptation using Caddy 2.11.7, with a formatting warning. No listener, certificate load,
    TLS trust, firewall policy or network isolation test was performed. Documentation addresses only.

29. Pinned Nix checks initially failed because Ruff tried to cache in a read-only Nix source.
    Disabling that cache made `nix flake check --no-update-lock-file` PASS on x86_64-linux;
    aarch64-linux was explicitly omitted as incompatible with this execution host.
    `nix develop --command make check` first passed 14 Go tests, 32 Python tests and the patched
    upstream race suites, then failed packaging because Nix's split GOROOT omits LICENSE.
    Added the official pinned Go 1.27.3 BSD notice fallback; no test failure is hidden.
30. Build-environment privacy: `test_public_build_tools_do_not_inherit_private_variables`
    RED inherited synthetic Vite/runtime canaries; GREEN uses a resource-only SDK environment,
    empty scratch npm configuration, uv --no-config, and disabled public-fetch credential config.
    No real secret value was used in this test. `tools/build` then PASS with 28 runtime Go module
    notices and Go's standard-library notice. This hardens future builds as well as runtime tests.

`uv build --out-dir "$TMPDIR/hermes-apron-build"`: PASS wheel and Python sdist.
Archive name/content audits: PASS (13 wheel files, 22 sdist files); no runtime state/credential files.
These are Python package artifacts, not a complete audited deployment release.

31. Independently reviewed HIGH machine scope finding (snapshot `272afba`):
    `tools/go test ./internal/server -run '^TestMachineRoomScope$' -count=1` RED:
    `room_list` returned an unconfigured public room. An activity notification was initially
    tested as an RPC and timed out; that fixture error was removed and is not RED evidence.
    GREEN: `tools/go test -race ./internal/server -run '^TestMachine(RoomScope|MustBeJoinedToPost)$' -count=1`
    PASS. Exact scope persists with the credential; public/private/unconfigured child rooms,
    targeted and aggregate history/lists, cross-scope replies, upload posts, joins and creates
    are denied. Explicit private/thread scope works after SQLite restart and remains restricted
    on another restart. A human cannot expand bot scope with membership. Hermes fixtures now
    provision as humans and restart with explicit operator scope; their results follow below.
    Current public protocol retrieved via curl: v10, updated 2026-10-30 (web tool unavailable
    for that URL); pinned protocol fixtures remain authoritative for tested compatibility.
    `nix develop --command tools/test tests/test_adapter.py -k 'two_private or edit_is_bound' -q`:
    PASS, 2 passed / 17 deselected. Actual pinned Hermes handlers and Chromium passkeys retain
    two private parent/two child conversation isolation and room-bound edits under explicit scope.

32. Independently reviewed MEDIUM machine active-socket expiry:
    `tools/go test ./internal/server -run '^TestMachineExpiry' -count=1` RED, both tests:
    `machine expiry left an authenticated socket alive`. The tests use actual 600/700 ms
    deadlines and wait on sockets; no timestamps, stored expiries or clocks are fabricated.
    GREEN: the same two tests under `-race -count=3` PASS. Both sockets close, a message
    held in a real extension filter plus a pipelined frame cannot commit, fresh auth fails,
    restart schedules the original deadline and another restart cannot renew an expired token.
    Added upstream lifecycle regression covers replacement, revocation and shutdown timer cleanup.
    Patch regeneration initially omitted the pre-existing untracked durability regression and
    formatted an unrelated test; corrective local commit `e8f9746` restores both without rewriting history.
    `tools/upstream-test -run 'TestMachineTimerLifecycle|TestClosedWrapperRequiresDurableSQLiteCommits' -count=1`:
    PASS under race detection for patched apron/store; aproncmd correctly reports no matching tests.
33. Independently reviewed HIGH reconnect/lease credential rotation:
    `nix develop --command env TMPDIR=<scratch> tools/test tests/test_peer_security.py -q`
    RED: the adapter authenticated token B while a real second process already consumed B,
    holding only A's lease (`adapter authenticated rotated credential without its consumer lease`).
    Initial child registration used a mismatched Hermes profile scope; that setup failure is not RED.
    GREEN with a fixed fingerprint/lease match before reconnect: changed file produces the real
    Hermes nonretryable `credential_changed` status, closes tasks/connections/state/lease, and
    never authenticates B. The child remains exclusive; controlled restart acquires B after child
    exit. Focused rotation/reconnect/second-consumer suite PASS: 3 passed / 17 deselected.
34. Completing independently reviewed machine-scope finding: live thread metadata.
    `tools/go test ./internal/server -run '^TestMachineRoomScopeLiveMetadata$' -count=1`
    RED: unconfigured child metadata broadcast to scoped parent member. Upstream announces
    new/changed public threads to parent members independently of room listing. GREEN after
    shared visibility checks on thread announcements and room/membership deliveries, plus
    suppressing left records for children outside machine scope:
    `tools/go test -race ./internal/server -run '^TestMachine' -count=1` PASS.
35. Independently reviewed MEDIUM untrusted protocol shape/lifecycle failures:
    `tools/test tests/test_peer_security.py -k 'not rotation' -q --tb=short` (pinned Nix shell)
    RED: 29 failed / 1 passed / 1 deselected. Missing/empty/scalar bot IDs were accepted;
    malformed room-list/history entries raised AttributeError/TypeError or were accepted;
    malformed room updates crashed a supervisor or left it running. GREEN shared shape/type
    validators reject these before indexing, membership lookup or durable checkpoint writes.
    Malformed protocol stops cleanly with bounded fixed `invalid_protocol` status; ordinary
    disconnects retain bounded retry. Actual Hermes status APIs are used; no remote error text
    or credential is copied to errors. Reconnect pins the authenticated bot ID as well.
    Expanded synthetic-peer suite PASS: 80 cases, covering auth, greeting/RPC shapes, room
    lists/updates, history/boundaries, live messages, media receipts, standalone failures,
    forced reconnect failures, and real second-process credential rotation. Corrected peers
    can reconnect using the released state/credential locks. Captured old/new transports have
    no tasks, pending RPCs or sockets after failed reconnect. Focused peer/transport/adapter
    suite before the last 13 peer cases: PASS, 91 tests; authoritative final totals follow.
36. Full upstream race suite caught a compatibility regression in the new candidate filter:
    `TestRoomListLatestLogIDDeltaPrivateRooms` failed because human private-room removal
    lost its `left` delta. Narrowed the filter to exact machine policy only, preserving upstream
    human visibility/membership behavior. Focused upstream race regression PASS.
    Completing the reviewed media-target path: extended `TestMachineMustBeJoinedToPost` RED
    allowed a pending `/embed-append` HTTP write to post after machine leave (204). GREEN
    denies command creation after leave and checks machine room scope/active admission/membership
    at HTTP write start, upload commit, live chunks and completion. Pending posts also recheck
    membership. Read capabilities and bytes already shared remain independent bearers.
    Real HTTP `TestMachineUploadRechecksTargetMembership` covers leave before write start and
    during body receive (genuine HTTP 100-continue rendezvous), with no read capability published.
    `tools/go test -race ./internal/server -run '^TestMachine(MustBeJoinedToPost|UploadRechecksTargetMembership|RoomScope)' -count=1`: PASS.
37. Supplemental scope wire assertions verify policy restoration without any machine rebinding,
    parent-filtered child listings, known outside message/embed IDs, out-of-scope stream commands,
    and implicit default targets after removing `general` from explicit scope.
    Final `tools/go test -race ./...` PASS with all 19 top-level wrapper tests.
    LOW stale-aggregate finding is corrected by the authoritative final-results table above;
    historical RED/GREEN counts remain explicitly historical.
