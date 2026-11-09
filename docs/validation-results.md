# Executed validation

Implementation evidence, not deployment approval. Network/device/operator gates remain NOT RUN.

## Second and final focused correction cycle — 2026-11-09

Base: clean main checkout `a022df2`. Corrections are local; parent independent review is
still required. **Neither independent review is recorded as passed.** The first review found
machine scope, active-socket expiry, reconnect credential-lease and malformed-peer lifecycle
issues; its corrections were integrated at the base. The second re-review found a remaining
HIGH native LiveWriter bypass and MEDIUM malformed Unicode failure. The supplied re-review
scratch result was `writeErr=nil`, `closeErr=nil`, with `AFTER-REVOKE` in final content;
the native regressions below independently reproduce that behavior in this correction cycle.

The parent also reported a full-check attempt with **95 Python passes and 18 fixture startup
errors** from an overlong control Unix socket path. That run is a failure, not a passing suite.
Its rerun with `env TMPDIR=/home/agent/.hermes/cache/scratch nix develop --command make check`
passed **113 Python tests** and Go/upstream/lint/build/audits at the base. Those are parent-reported
results, separate from this cycle's executed results. The new diagnostic rejects overlong state
paths without printing the private path or changing socket permissions/location. Tests here use
the same short private scratch root and command-scoped environment prefixes; no shared `/tmp`
fallback or persistent global environment change is introduced.

| Command (command-scoped short private TMPDIR, pinned `nix develop`) | Actual second-cycle result |
|---|---|
| `make check` | **PASS, exit 0**: wrapper and upstream races, full Python/browser suite, lint, binary build/notices, content and dependency audits |
| `tools/go test -race ./...` (within `make check`) | **20 top-level wrapper Go tests PASS**; command package has no tests |
| `tools/test -q` (within `make check`) | **160 passed**, 52.81s; real pinned Hermes, real Go wire/server and Chromium/WebAuthn/local frontend; no skips |
| `tools/upstream-test` (within `make check`) | **PASS**: patched `apron` (52.278s), `aproncmd`, `store`, with race detection and real pinned protocol fixtures; includes 48 new machine-stream subcases and two human bearer subcases |
| Focused Unicode/conversion/preservation suite | **47 passed / 80 deselected**; explicit clean restarts and fixed fatal status/cleanup assertions |
| `tools/frontend --test` | **PASS, exit 0**: **200 files / 1,691 tests**, Svelte 0 errors / 0 warnings, runtime npm audit 0 vulnerabilities, local static build PASS. Five low development-only findings remain; frontend sources/pins unchanged |
| `nix flake check --no-update-lock-file` | **PASS** on x86_64-linux; aarch64-linux omitted as incompatible, not counted as passed |
| Go vet/gofmt and Ruff check/format | **PASS**; **24 Python source/test/tool files** formatted |
| `tools/build` | **PASS**: binary, **28 runtime Go module** notices plus Go standard-library notice, all in scratch |
| govulncheck v1.9.0 / Python OSV audit | **PASS**: no Go vulnerabilities; **40 locked public Python packages**, zero reported OSV findings |
| `python3 tools/audit.py` | **PASS**: **72 source files / 16 prior added commits** at the precommit snapshot; requirements/validation contract unchanged |
| `gitleaks dir/git --redact` | **PASS**: source, prior added history (`b899490..HEAD`; 15 non-merge commits scanned) and extracted package contents, no leaks |
| Isolated `public_run.py uv --no-config build` | **PASS**: wheel and sdist built from a scratch source copy, no inherited private build variables; path/content audit **14 wheel files / 25 sdist files**, nine packaged modules match current sources |

The separate uv `.gitignore` build helper was audited and excluded from archive counts after
an initial archive-enumeration script attempted to open it as a tar file. That script failure
is not a package-build pass/failure or a security finding. Runtime canary/permission/log tests
are included in the full suite; raw execution logs and all generated artifacts stay in scratch.
Final committed source/history are rescanned before handoff. The public v10 protocol was fetched
again (web open was unavailable; isolated curl succeeded) and its SHA-256 remains
`c5d74dd956e8dce9f6fe62eb7022a219e0c668be1bc1f536af39fc2e7f44f1d4`.

No push, deployment, PR, service activation or production/gateway/Telegram/system configuration
change was performed. Parent review, safe affirmative consent, selective credential removal,
full license/security review, resource/crash/recovery coverage and actual LAN/TLS/device/IPv6
acceptance remain explicit release gates. These tests do not clear any of those gates.

## First correction cycle — historical validation through a022df2 (2026-11-09)

These are the first cycle's recorded results, superseded by the second-cycle results above.
Counts in the numbered TDD chronology are historical. The requirements and release gates remain unchanged.

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

## Original implementation verification (2026-11-09; before independent-review fixes)

`nix develop --command make check`: **PASS (exit 0)** with the final implementation.
This ran `tools/go test -race ./...` (14 top-level server tests), `tools/test -q`
(33 PASS, 23.79s, including real Hermes APIs, real Go server and Chromium virtual
authenticator/local frontend), and `tools/upstream-test` (real patched apron,
aproncmd and store race suites PASS). Go vet/gofmt, Ruff lint and formatting
(22 files), binary build, 28 runtime Go-module notices plus Go's notice,
source/added-history audit, govulncheck v1.9.0 and Python OSV audit all passed.
Govulncheck reported no vulnerabilities; OSV queried 40 public locked packages
with zero reported findings. Advisory results are time-dependent.

`nix flake check --no-update-lock-file`: **PASS (exit 0)** on x86_64-linux.
The final source derivation was cached; an earlier uncached execution passed
after the documented Ruff-cache fix. The incompatible aarch64-linux system
was omitted, not tested.

`python3 tools/audit.py`: PASS, 67 source files and six added implementation
commits before this evidence-only commit. `git diff --check`: PASS.
`nix develop --command gitleaks git --redact --no-banner --log-opts='b899490..HEAD' .`:
PASS, six commits scanned, no leaks. The working-directory gitleaks scan also
passed. These checks supplement the exercised disposable runtime canaries;
they are not an independent security or publication review.

The first final `tools/frontend --test` attempt failed during Svelte setup with
missing installed development-package imports after npm ci. This is a tooling
failure, not behavioral TDD RED evidence; the cause has not been established.
A fresh invocation is recorded separately below. No failed run is counted as
a pass and no automatic dependency upgrade was used to bypass it.

Fresh `tools/frontend --test`: **PASS (exit 0)**. Clean npm ci, explicit prepare,
Svelte check (0 errors/0 warnings), runtime audit (0 vulnerabilities), 200 test
files / 1691 tests (64.17s) and the local-only static build passed. The five
low-severity development-only findings and jsdom canvas warning remain as
documented above. This rerun required no source or lockfile change.

Original REQUIREMENTS.md and VALIDATION.md are unchanged from b899490. Only
disposable loopback fixtures ran; no LAN deployment, active service changes,
production credential reads, push, PR, fork or release occurred. Manual TLS,
device/network and backup/restore checks and the other matrix release gates
remain NOT RUN or BLOCKED.
## Independent-review regressions and fixes

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

## Second-cycle behavioral RED/GREEN ledger

38. Native machine stream authority: in dedicated scratch materialized from pinned server
    `cefba0193cf5cf8407dfb47c0970b9a26e6c1b8c` plus the original patch,
    `go test ./apron -run 'TestMachineNativeLiveAuthority|TestHumanLiveAfterLeave' -count=1`
    RED: **all 40 machine subcases failed**; human append/terminal cases passed. Write accepted
    `AFTER-DENIAL`; Close/internal/timer paths published buffered data after revoke, genuine
    expiry, exact-scope narrowing or membership leave. First setup attempts raced asynchronous
    bootstrap-session shutdown; only the corrected run, which waits for that session, counts
    as RED. Supplemental unstarted-Close RED: **8 failed subcases**. GREEN:
    `go test -race ./apron -run 'TestMachineNativeLiveAuthority|TestHumanLiveAfterLeave|TestExtensionStreamAppend' -count=1`
    PASS: **48 machine authority-loss subcases**, both human bearer cases and existing native
    append behavior. Timer tests reset the real duration timer and select its idle-writer branch;
    expiry tests wait for the genuine bound deadline, never backdate stored policy. Native
    Write/Close and the central final-content commit now recheck authority under the server lock;
    denial fails/removes the embed and invalidates capabilities rather than publishing its buffer.
    Patch regeneration verified every other original section byte-for-byte, including existing
    machine timer tests and SQLite durability tests/hunks. Full checks rematerialize that patch.
39. Strict Unicode peer data: real synthetic WebSocket JSON sends high/low unpaired surrogate
    escapes in authorized live messages, history, immutable IDs, sender names/roles, mentions,
    room metadata, auth and media responses. Focused RED run: **43 failed / 80 deselected**;
    the authorized text case raised `UnicodeEncodeError` from `accepts`. One nesting case had
    an incorrect rejection expectation: Python 3.14 accepts deep JSON, so it was changed to a
    valid-input preservation test and is not counted as a defect. GREEN expanded focused suite:
    **47 passed / 80 deselected**. Invalid Unicode now becomes `InvalidFrame` before consumption,
    sets `fatal_error_code=invalid_protocol`, stops without worker exceptions or retries, releases
    transport tasks/RPCs/socket and state/credential reservations, and permits explicit clean
    restart. Startup failures report the same fixed fatal code. All decoded JSON strings and
    keys are checked strictly; no replacement/normalization can change an identifier. Valid
    non-ASCII/astral text is preserved. Conversion-boundary review covers oversized JSON integer
    conversion and deeply nested responses: scalar traversal is iterative; a decoder
    `RecursionError`, if raised, is converted only at `json.loads`, with no broad supervisor catch
    added to conceal programming errors.
40. Long private state paths: `tools/go test ./internal/server -run '^TestLongControlPathDiagnostic$' -count=1`
    RED: ASCII and multibyte paths returned only `cannot bind operator socket`. GREEN: both
    receive the fixed actionable shorter-private-state/TMPDIR diagnostic. The OS socket-path
    capacity is checked in bytes before filesystem mutation. Access modes and socket location
    remain unchanged.

## Parent verification and final focused independent reviews

At implementation commit `601b723760ff6392bdaa0f57eb3be2a9edccb54a`:

- Parent `env TMPDIR=<short-private-scratch> nix develop --command make check`: PASS,
  exit 0. Wrapper Go race suite, 160 Python/browser tests (55.61s), patched upstream
  apron/aproncmd/store race suites, Go vet/gofmt, Ruff lint/format, build/notices,
  source/history content audit, govulncheck and Python OSV audit all passed.
- Parent added-history gitleaks scan (`b899490..HEAD`): PASS, 16 commits, no leaks.
- Independent Go review of `a022df2..601b723`: PASS, no security/logic findings.
  Inspected native Write/Close/start/final-commit locking and denial behavior, and ran
  native authority-loss, human/unrestricted-bot, append/terminal/timer regressions and
  `TestLongControlPathDiagnostic` under the race detector.
- Independent Python review of the same range: PASS, no security/logic findings.
  Executed 47 Unicode/conversion/lifecycle cases (20.11s) and 29 malformed-peer/recovery
  cleanup cases (8.38s). Valid astral text remains unchanged; invalid frames cleanly
  release reservations and permit explicit restart.
- Earlier parent check with a deeply nested private TMPDIR failed fixture startup:
  95 Python tests passed and 18 errored. A short-path rerun passed 113 tests before
  the second correction cycle; the current 160-test parent result above supersedes it.
  No failure was counted as a pass. The diagnostic now explains the socket-path limit.

These are focused independent reviews and reproducible parent checks, not a complete
security/license audit or deployment approval. Development source is approved for public
publication with known blockers retained. Safe affirmative consent, selective credential
removal, broader native features, resource/crash testing and real LAN/TLS/device/recovery
drills remain blocked or unverified as listed in the status matrix. No live services or
production configuration were modified.

## First remote CI run and checkout regression

GitHub Actions run `42675406683` at `ec05472` passed the wrapper/upstream Go race
suites, Go vet/gofmt and Python lint/format checks, then failed the source/history
audit: the default shallow checkout did not contain baseline `b899490`. Frontend
and browser/plugin steps were skipped, not passed.

The checkout now requests `fetch-depth: 0` while retaining `persist-credentials: false`.
A configuration regression test parsing the workflow observed RED (1 failed / 1 passed)
then GREEN (2 passed) with the full-history checkout. Ruff check/format, the local
content/history audit and `git diff --check` passed. A replacement remote CI result
was verified separately below; these local checks do not retroactively make the first run pass.

Replacement [GitHub Actions run 42676319598](https://github.com/urchin-tidebot/hermes-apron/actions/runs/42676319598)
at exact commit `0b71a5f5e713ce947eda880990c74a56741232cd`: **PASS**, conclusion
`success` read back through the GitHub API. Wrapper/upstream race suites, vet/gofmt,
Ruff checks, binary build and content/history audit passed. Frontend completed all
200 files / 1,691 tests; real Python/browser/plugin suite passed 161 tests (30.67s),
including the new checkout-history regression. This verifies Ubuntu CI in addition
to local Nix checks; it does not remove any deployment or missing-feature blocker.
