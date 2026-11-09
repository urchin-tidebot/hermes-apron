# Implementation status

**Working development implementation; not deployed, independently audited, released or production-ready.** The original acceptance contract is unchanged. “Automated” below describes executed evidence, not completion of every subcase. Manual and blocked items are not counted as passes. See the [execution ledger](validation-results.md) and [threat model](threat-model.md).

## Security / architecture

| IDs | Status | Evidence and limits |
|---|---|---|
| A1, S3–S5 | Implemented; automated | Real pinned apron/aproncmd wrapper; no guest/open/email/external signup; random short-lived one-account invite; real verified resident/UV WebAuthn; atomic account/credential/allowlist/invite SQLite batch. Concurrent, replay, restart and one transaction failure tested |
| S5 durability | Partial release gate | FULL SQLite pragma verified; fail-stop persistence; no exhaustive process kill/power-loss injection at all filesystem/commit boundaries; independent patch review still required |
| S1, S2 | App implemented; deployment manual | Loopback default/enforcement, exact HTTPS origin/RP, ephemeral-only explicit HTTP test mode. Proxy example uses documentation addresses. Actual TLS/LAN/non-LAN IPv4/IPv6/phone checks NOT RUN |
| S6 | Implemented with documented capability limits | Durable invite/account/bot revocation, active WS disconnect and auth/resume denial; upstream sign-out forgets session/device/push state. Already-issued media capabilities are separate bearers, not revoked by account removal |
| S7 | Partial / BLOCKED | UV passkey login and bounded absolute origin-bound human resume; no ceremony on every reconnect. Device creation disabled. Upstream has no inspected supported credential-removal API; whole-account revocation recovery tested, backup/recovery drill not run. Expiry gates new auth; explicit revocation closes active sockets |
| A2, S8 | Implemented; automated | Actual pinned Hermes loader/context/registry/BasePlatformAdapter/profile helpers; separate non-admin bot runtime credential; explicit memberships/rooms; independent actor allowlist; no trusted_inbound. Real cross-profile credential reservation and send-only coexistence tested |
| A3, S9, V12 | Implemented locally; deployment manual | Paired pinned frontend served locally; local default WS/share/terminal policy, CSP, UV passkey/chat browser E2E; runtime-only credential files, private socket/state, no token-bearing HTTP client logs. Tests use disposable canaries. Phone trust and all production egress/network behavior untested |
| A4, V11 | Partial | Real persistent SQLite restart and atomic failure tests; upstream history/upload storage retained. No complete backup/restore/monotonic-ID/upload recovery drill or corrupt-disk campaign |
| S9 | Automated checks + publication review pending | Working tree/added-history content audit, gitleaks, private mode/canary DB/log/binary tests. No production credential/config/state/transcript access. Independent artifact/license/publication review still required |
| S10 | Partial / BLOCKED | Bounded frames/RPCs/queues/recovery/inbox/uploads/streams, local-only write targets, no redirects/traversal/symlinks or arbitrary inbound URL fetch. Total chat-storage quota, all resource-exhaustion cases and long stress testing incomplete |
| S11 | BLOCKED, fails closed | No affirmative chat approval transport. Approval command input rejected. Unsupported clarification cancels the exact matching real waiter instead of leaving an ambiguous text intercept. Safe owner/request/thread/replay-positive path not implemented; native draft actions deferred |
| S12 | Implemented conservative subset | Content never becomes policy/configuration; no shell execution. Reviewed terminal-summary API requires explicit opt-in + approval, is bounded and scrubbed. No arbitrary tool/environment/transcript streaming; no general secret-redaction guarantee |
| E1–E4 | Artifacts implemented; some checks pending | Docs, MIT, pins/lockfiles, build/test scripts, Nix devShell/source checks, read-only pinned Node-24 CI. Remote GitHub Actions NOT RUN. This is not a pure Nix-built Go binary derivation |
| E5 | Automated representative evidence | Real pinned Go wire exchanges, actual Hermes APIs/handler/loader and Chromium virtual authenticator + actual Svelte client; no model calls. Full running model/tool gateway integration NOT RUN |
| E6, E7 | BLOCKED / NOT RUN | Self-review and regressions completed. Independent security/license review and parent publication approval outstanding. No push, PR, fork, release, service activation or LAN deployment performed |

## Native features and fallbacks

| Feature | Implemented and exercised | Limitation / fallback |
|---|---|---|
| F1 | Greeting/version/capability inspection, token auth, out-of-order RPC correlation, errors/retry_after, cancellation/deadlines, heartbeat implementation, bounded reconnect/backoff, locks/cleanup | Synthetic peers exercise unusual replies; real server exercises normal/error/reconnect paths. Long suspended-device heartbeat tests incomplete |
| F2 | Markdown/plain, stable IDs, structured mentions, sender identity, replies, own/bot suppression | Display-name mentions grant no authority; only configured immutable IDs invoke Hermes |
| F3 | Explicit joined rooms/private rooms/threads as independent native room IDs | Two private rooms/two child threads tested concurrently; no implicit autojoin or dynamic thread discovery beyond configured IDs |
| F4 | Durable dispatch reservations/checkpoints, high-water history recovery, live buffering, edit/reaction/tombstone suppression | First install starts at current boundary; bounded backlog/gap fails closed. Reserve-before-dispatch can lose a turn on crash. No exactly-once tool effects/outbox guarantee |
| F5 | Real append streaming, revisions, finish in same message; Hermes expect_edits/finalize hooks; supported edit fallback | Core-only completed-text fallback tested. All cancellation/error/crash windows not exhaustively covered; no claim of guaranteed final delivery after unknown outcomes |
| F6 | Native terminal embed for opted-in, individually approved reviewed summaries; ANSI/control stripping, limits and known-canary scrubbing | Raw Hermes tool lifecycle streaming intentionally disabled; unsupported capability uses bounded text. Browser terminal rendering/cancellation matrix incomplete |
| F7 | Real upload artifacts and private flat export policy; image/audio/video hooks use same upload transport | Actual file upload/readback tested; inline voice/video client playback NOT RUN. Inbound attachments are not fetched; standalone media refused; no false media success |
| F8 | Native typing start/clear, membership changes and chat-info metadata | Hermes reaction/title action facade is hardcoded to Telegram/Discord at this pin; no safe public plugin registration hook found. Reaction/presence/title integration deferred rather than mutating core/private dispatch tables |
| F9 | Home-room or explicit configured target, standalone sender, separate-process delivery and receipt readback beside live consumer | No consumer lock/session invalidation by cron; unknown/offline/bad-credential outcomes are errors. Not every scheduling/timezone/daemon lifecycle exercised |
| F10 | Safe `!help`, `!status`, `!new` routing via Hermes handler; Apron slash commands remain server-owned | Consent/clarification blocked as above; no server invitation/admin command through the bot |
| F11 | Push OFF | No public relay/service required. Enabling push is a new explicit privacy/egress review |
| F12 | Core-only/future-capability handling, completed text/edit/summary notice fallbacks | No fabricated optional RPCs; feature-specific failures stay failures. Capability-limited scenarios are complementary synthetic peers, not claimed native server configuration |

## Acceptance scenario index

| Validation | Current evidence |
|---|---|
| V01 | Real closed greeting/requests and signup regression; upstream auth tests. Partial metadata/media capability assessment |
| V02 | Real UV WebAuthn software + Chromium ceremonies; real restart login; local Svelte client login/chat |
| V03–V05 | Verifier-only storage, malformed/no-UV/wrong origin/RP/replay/abandonment/concurrent/revoked invite regressions. Exhaustive expiry/guess/failure-injection/browser-negative permutations incomplete |
| V06–V07 | Explicit owner flags, human/bot separation, active revocation/new auth/resume denial, durable restart. Selective credential removal blocked |
| V08 | Unsafe address/origin/test settings rejected; real services ephemeral loopback; trusted production TLS not run |
| V09 | NOT RUN: separate approved LAN, non-LAN IPv4/IPv6, actual device/TLS tests |
| V10 | Source/history secret/content scans, runtime canary/modes/binary checks; parent artifact/license review still required |
| V11 | SQLite/inbox restart and one failed enrollment transaction; full backup/restore/history/upload/ID recovery drill incomplete |
| V12 | Patched local frontend/browser network assertions, dependency/runtime audit, no external terminal/share redirect; operator runtime egress check pending |
| V13–V14 | Actor/room/mention gates, real authorized human handler, two private rooms/two threads and routing/readback; broader membership/private-media cases incomplete |
| V15 | Negative command/clarification cancellation boundaries; affirmative approval/clarification BLOCKED |
| V16 | No shell/config from content; hostile display-name authority rejected by ID design; exhaustive adversarial content corpus incomplete |
| V17 | Real normal/error RPC and lifecycle; synthetic out-of-order/timeouts/cancel/denied. Oversize/malformed/long heartbeat stress coverage incomplete |
| V18 | New adapter offline recovery, durable suppression, no new turns for changed records; full crash/retention/gap concurrency campaign incomplete |
| V19–V20 | Separate sender/consumer lock and process coexistence; core-only/future-capability fallback. All revocation/offline/exhaustion permutations incomplete |
| V21–V22 | Native append same-ID completion/revision, terminal summary opt-in/scrub; exhaustive cancellation/client rendering matrix incomplete |
| V23 | Native upload/path/no-follow/target gates; broad media tamper/storage/interrupt tests and playback incomplete |
| V24 | Typing real wire; reactions/presence/title facade integration deferred |
| V25 | Real standalone separate-process receipt while live consumer remains usable; broader scheduled home/thread cases incomplete |
| V26 | Commands routed through actual Hermes; clarification/approval fails closed, push off. Full positive command/consent UX incomplete |

No single test, green suite, configuration example or automated scan removes these release gates. Exact final command counts/results are in [validation-results.md](validation-results.md).
