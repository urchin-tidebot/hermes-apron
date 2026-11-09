# Validation scenarios and acceptance evidence

Status: scenarios specified; NOTHING below is a passing result until linked to actual execution evidence. Tests must generate disposable identities/secrets and isolated state. Never test against the production gateway. Track each scenario with requirement IDs, automated test name/command, result and remaining manual checks in docs/validation-results.md. Distinguish unit, real-server integration, browser E2E and operator/network evidence.

## Enrollment and authentication

- V01 (S3,S4): Fresh persistent server denies guest, uninvited registration, email/external login and unknown bearer tokens; unauthenticated client cannot read room/history/member/chat data.
- V02 (S4,S5): Operator-generated one-account invitation allows registration with a virtual WebAuthn authenticator and required user verification; resulting stable account is allowlisted and can log in again after server restart.
- V03 (S4-S6): Expired/revoked/reused/malformed/guessed invitations fail without account creation or information disclosure. Plaintext invitation does not appear in DB, captured logs or errors.
- V04 (S5): Two independently challenged concurrent redemptions of one invite yield exactly one authorized account. Repeat under race detection and across a restart/failure injection at each persistence boundary. Failed or abandoned WebAuthn can retry until expiry without consuming invitation.
- V05 (S2,S5): Wrong origin/RP ID/challenge, absent user verification, challenge replay, altered credential, interrupted enrollment and unexpected messages all fail closed. Disabling guests alone must not leave open registration.
- V06 (S6,S7): Only owner/operator can issue later invitations or change allowlist. Human display-name spoofing cannot grant rights. Account revocation disconnects active sockets and rejects passkey/session/device resumption after restart; demonstrate supported recovery/removal limitations explicitly.
- V07 (S7,S8): Human session resumes with documented bounds; dedicated bot credential is separate, non-admin and revocable. Missing secret fails safe. Read-only status/config checks never print secret or provision accounts.

## Network, persistence and credentials

- V08 (S1,S2): Default process listens only on loopback. Production configuration rejects wildcard/insecure origins and accidental insecure LAN auth; static UI, WebSocket, WebAuthn and capability URLs use configured local HTTPS origin.
- V09 (S1): Operator-only LAN acceptance: intended LAN device succeeds; non-LAN IPv4 AND IPv6 clients cannot connect; no public listener/forward/tunnel exists. Do not mark from static config alone. Test TLS trust and passkeys on the actual phone/browser separately.
- V10 (S9): Build/test/secret scan covers tracked files, generated artifacts, Git history added by this project and captured logs. Real secrets/state absent; examples contain no private deployment data. Credential/state directories/files have appropriate permissions. Nix derivations contain no runtime secrets.
- V11 (A4,S5,S6): Restart/backup/restore preserves accounts, allowlist, invite consumption/revocation, history, uploads and monotonic identifiers. Failures in either upstream or extension store cannot leave half-authorized accounts. Corrupt/unavailable policy store prevents access rather than allowing all.
- V12 (S2,S9): Frontend is locally served/pinned with no implicit public-client scripts, fonts, invite redirects, analytics or public push/relay dependency. Sensitive capability URLs are scrubbed from access/error logs. Document intended package-fetch egress versus runtime egress.

## Hermes authority and conversation routing

- V13 (S8,F2): Server-allowed but Hermes-disallowed human cannot start an agent/tool run. Unknown actor, anonymous/absent actor and bot self-echo are ignored. Mention checks use structured IDs, not display-name text.
- V14 (F2,F3): Two rooms and two child threads exchange messages/replies concurrently; replies and sessions never cross. Private-room history and uploads do not leak through bot messages into other rooms. Room membership changes apply promptly.
- V15 (S11,F10): Legitimate owner answers exact approval/clarification. Different actor, thread, session, expired request, replay, forged message/reaction or ambiguous answer cannot approve. Concurrent pending requests never settle the wrong action. Unsupported safe approval path visibly fails closed.
- V16 (S12): Hostile room titles/names/history/files/terminal content do not change access policy, get interpreted as configuration or execute commands. Commands cannot issue invitations or administer the server through an unprivileged bot.

## Protocol correctness and recovery

- V17 (F1): Real server greeting/auth/RPC/error/heartbeat exchanges; out-of-order RPC replies, missing replies, malformed/oversized frames, cancellation, denied and retry_after have bounded correct behavior. Shutdown releases all tasks/connections/locks.
- V18 (F4): Disconnect during agent turn, send messages while disconnected, reconnect, and recover history while live messages arrive. Edits/reactions/tombstones never trigger a fresh run. Replayed IDs do not rerun completed turns; durable checkpoint behavior survives new adapter instance and process restart. Test gaps/retention and document unavoidable crash windows for tool side effects.
- V19 (F1,F9): Live gateway and standalone cron sender coexist using supported separate connections; credential lock prevents duplicate consumers while allowing bounded send-only delivery. Authentication revocation stops both. Delivery errors are surfaced, not reported as success.
- V20 (F12): Exercise capability-limited server (core-only), unsupported methods and unknown future capability fields. Plain text still works; no fabricated room/history/upload support, busy reconnect loop or silent message loss.

## Native feature behavior

- V21 (F5): Native append stream grows in one message, finishes cleanly, handles cancellation/server failure and produces no duplicate final response. Capability-absent path posts completed text.
- V22 (S9,S12,F6): Opt-in terminal stream handles ANSI, invalid escapes, binary/huge output, cancellation and finish. Secret canaries are absent from broadcasts/logs; an unapproved arbitrary command is not streamed even if redaction regexes exist. Fallback is a bounded safe artifact/text.
- V23 (S10,F7): Real uploads and outbound file/image/audio/video artifacts; declared type/size/path/URL tampering, redirect to forbidden targets, traversal, metadata leak, storage exhaustion and interrupted upload fail safely. Verify actual authorization semantics of file/read/stream capability URLs and record revocation limits.
- V24 (F8): Typing clears on completion/cancel/error; reactions, presence, edits and thread titles are correctly attributed and do not retrigger the model.
- V25 (F9): Scheduled home-room and explicit thread delivery from a separate process works against real server with real receipt readback; offline/bad-credential errors remain errors.
- V26 (F10-F12): Commands and clarification fallback work with supported Hermes APIs; no conflict with Apron slash commands. Push is off; external provider enablement is explicit and not required for LAN usage.

## Required execution layers and release gates

1. Unit/property/race tests for policy, invite transaction, parsing, redaction, authorization and lifecycle. Observe meaningful failing test before each new production behavior.
2. Real-server integration tests with isolated persistent SQLite and ephemeral loopback sockets, including restart/crash-boundary tests.
3. Browser E2E for registration/login and native rendering using virtual WebAuthn authenticator; no production authenticator/credential access.
4. Plugin registration/import and representative real Hermes adapter integration at a pinned version; test doubles alone are insufficient. No model API calls needed for deterministic transport/security tests.
5. CI build/lint/tests, dependency/license/secret review and independent security review. Record commands, versions, actual results and blockers; zero security blockers before deployment.
6. Operator-approved staging later: trusted LAN HTTPS, phone/browser passkey UX, real LAN/non-LAN IPv4+IPv6 isolation and recovery drill. These remain NOT RUN during this implementation task.

No production readiness claim follows merely from completed code, a green unit suite, a mock authenticator, successful CI or a configuration example.
