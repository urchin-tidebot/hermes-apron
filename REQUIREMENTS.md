# Hermes × Apron requirements

Status: implementation contract; not a claim of security or deployment readiness.
License: MIT. Repository: https://github.com/urchin-tidebot/hermes-apron

## Goal and boundaries

Replace Telegram as the everyday Hermes interface using native Apron protocol v10 features, initially accessible only on an explicitly configured LAN. Use apron-chat/apron-server-go as the server foundation, its supported extension API where needed, and a separately installable Hermes platform plugin. Prefer upstream defaults except for documented security overrides. Do not fork/copy an entire server or implement cryptography/WebAuthn from scratch.

This project implements and validates artifacts; it must NOT alter this host's gateway, root NixOS configuration, firewall, router, production state, or Telegram delivery. Test services bind loopback on ephemeral ports. Real LAN deployment is a separate approval gate.

## Authoritative references

- https://apron.chat/protocol.md (current v10; verify before coding)
- https://github.com/apron-chat/apron-server-go (MIT; pin an exact version/commit)
- https://github.com/apron-chat/apron-server-go/blob/main/SERVER.md
- https://github.com/apron-chat/apron-web (pin compatible frontend)
- https://hermes-agent.nousresearch.com/docs/developer-guide/adding-platform-adapters
- https://github.com/NousResearch/hermes-agent (test against an explicitly recorded version/commit)

Record dependency provenance/licenses and tested compatibility, including any necessary upstream API gaps. Check actual APIs, not just documentation examples.

## Architecture

A1. A small Go server wrapper/extension uses upstream apron and aproncmd, adding closed enrollment and account access policy without bypassing upstream validation.
A2. A Python Hermes platform plugin registers through Hermes's platform registry; no core Hermes fork. Config validation, profile-scoped secrets, authorization, home-room/cron and standalone delivery must work.
A3. Host the pinned Apron frontend locally on the same HTTPS origin. A small audited enrollment UI may be added if necessary. Never send invitations, passkey operations, chat, or artifacts through public Apron services.
A4. Persistent SQLite stores enrollment/access state transactionally; upstream chat/account persistence and uploads are preserved across restarts. State directories are private; document backup/restore and credential recovery.

## Security requirements (release blockers)

S1. Default application bind is loopback. Provide explicit LAN-only deployment configuration with TLS and restricted IPv4 AND IPv6 ingress. No wildcard listener as an implicit default, WAN exposure, public tunnel, automatic public ACME HTTP listener, or router port forwarding. Document which controls belong to app, proxy, firewall and operator. Do not call a configuration example proof of firewall isolation.
S2. Use a stable operator-chosen hostname, trusted HTTPS/WSS, exact WebSocket/WebAuthn origins, correct narrow RP ID, configured public URL and self-hosted assets. Refuse unsafe production settings. Loopback-only test exceptions must be explicit and impossible to enable accidentally in production. Origin checks are not network access control.
S3. Guests, open passkey signup, email login and external sign-in are disabled. Only explicitly allowlisted immutable human account IDs can sign in/resume. Display names convey no authority. Private/history/media/stream access and any pre-auth metadata leakage must be assessed separately.
S4. Fresh installation has no human accounts, no default password/token/admin and no implicit 'first visitor wins'. Local operator CLI creates a cryptographically random, short-lived invitation permitting exactly ONE new account. It is not an existing-account device login token. Store a verifier/hash, never plaintext. Deliver invitation once through an intentional local output/file mode, not service logs.
S5. Redemption is bound to a verified WebAuthn registration and finishes atomically: successful credential registration, account creation, account allowlisting and invitation consumption. Failed/abandoned registration must not consume it. Concurrent/replayed redemptions, process restart and failure between writes must never produce two accounts or an unauthorized persisted account. If upstream cannot support this safely, document and implement the minimum supported extension/patch strategy; do not silently weaken this contract.
S6. Bootstrap owner/admin rights are explicit, not inferred from display name or network location. Later invitations require authorized operator/admin action. Invitation expiry/revocation and account revocation survive restart. Revocation denies new auth, resumes and active sessions plus account-related device/session tokens and pushes. Define treatment of already-issued media capability URLs.
S7. Humans enroll/login using user-verified passkeys, then may resume with revocable bounded bearer sessions. Document that this is not a passkey ceremony on every reconnect. Document backup passkey and lost-credential recovery, with no hidden email/guest backdoor. Inspect upstream credential-removal limitations and either provide safe supported removal or mark an explicit release blocker with a tested account-revocation recovery path.
S8. Hermes uses a separate least-privilege bot identity with role bot and a revocable runtime machine credential. It must not use a person's session or administrator privileges. Explicit room membership and a separate Hermes user allowlist govern agent invocation. Server admission does not automatically grant tool access. No trusted_inbound bypass for chat.
S9. Secrets, tokens, invite URLs, credential material, personal account IDs, private hostnames/IPs, production transcripts, SQLite databases, uploads, TLS private keys and real environment files never enter Git, generated Nix store paths, CI artifacts or service logs. Use runtime credential/file injection, safe example placeholders and restrictive modes. Hash at rest where appropriate; redact token-bearing URLs, errors and streams. Tests generate disposable runtime secrets rather than reuse production credentials.
S10. Bound frames, requests, retries, uploads, storage, pending tasks and streams. Process untrusted attachment/stream URLs through appropriate SSRF controls; do not disable checks globally for LAN. An operator-selected local Apron endpoint can be deliberately permitted without trusting arbitrary message-supplied LAN addresses. Validate redirects and prevent path traversal.
S11. Approvals and clarifications preserve Hermes semantics. Answers bind to exact pending request, originating session and authorized human actor; no replay, cross-thread or reaction-only approval. Safest supported text fallback is acceptable; native actions remain experimental while the protocol draft is not stable. Fail closed if Hermes lacks a safe extension hook.
S12. History, messages, names, terminal output and file content are untrusted data, never configuration or authorization instructions. No shell execution from server commands or embed content. Terminal/tool publication is opt-in, bounded and scrubbed before broadcast; no automatic full transcript/environment streaming. A command that may leak secrets is not made safe by token regex redaction alone.

## Native Apron integration

F1. Persistent WS connection: greeting/version/capability inspection, token auth, correlated RPC results/errors, heartbeat, cancellation, reconnect/backoff, scoped credential lock and cleanup. Respect denied/retry_after and unsupported capabilities.
F2. Inbound/outbound Markdown/plain messages with stable IDs, structured mentions, sender identity, replies and own-message echo/bot-loop suppression.
F3. Joined rooms, private rooms and threads; thread-as-room mapping preserves isolated Hermes conversations and reply destinations. Configurable mention/DM policy; no room autojoin beyond explicit policy.
F4. History replay/recovery with durable room checkpoints and bounded buffering; edits/reactions/deletions are not new agent invocations. Avoid missing live events or rerunning completed tool requests after reconnect/restart. State exactly what execution/delivery guarantees are achievable across crash windows; never claim exactly-once side effects without proof.
F5. Native streamed answers via embed:append, correct completion/cancel/error handling, edits when supported, and final-text fallback without duplicate final messages.
F6. Native embed:terminal integration for explicitly approved tool output, with lifecycle/cancellation, ANSI safety and output limits; final bounded artifact/text fallback when unsupported.
F7. File/image/audio/video artifacts via embed:upload where supported, safe inbound media handling, restricted runtime files and meaningful fallback if no uploads. Do not pretend inline voice/video is supported without a compatible client test.
F8. Typing/activity, status/presence, reactions, room/thread titles and metadata through appropriate public Hermes extension points.
F9. Home-room and explicit room/thread scheduled delivery; ephemeral standalone sender supports out-of-process cron without stealing or invalidating the live bot session.
F10. Commands expose relevant Hermes behavior safely, without taking over Apron server administration commands. Clarification/approval behavior follows S11.
F11. Optional push is documented and OFF for initial LAN-only deployment; external push services/relays create an intentional egress/privacy decision, not a default requirement.
F12. Each optional capability has an explicit working fallback. Maintain a feature matrix listing implemented, tested, manual-only, blocked and deferred features honestly.

## Engineering and delivery

E1. README, MIT LICENSE, threat model, requirements, validation scenarios, architecture notes, operator setup/recovery guide, compatibility/provenance and evidence-backed feature/status matrix.
E2. Reproducible development/build/test entry points, preferably flake devShell/package/checks with pinned inputs plus lockfiles. Never install packages globally or modify agent Home Manager/root config as part of implementation.
E3. Test-driven vertical slices: write a behavioral test, run it and observe the expected failure, implement minimum, run passing focused/full tests, then refactor. Record concise real RED/GREEN evidence, not fabricated logs.
E4. CI uses supported-LTS GitHub Actions runtimes, minimal read-only permissions, pinned dependencies/actions where practical, no production secrets, no scheduled update PRs. No pretend skips labeled passes.
E5. Exercise the real pinned Go server with the Python transport/plugin and real wire exchanges; unit mocks alone do not demonstrate compatibility. Include browser WebAuthn virtual-authenticator E2E where feasible. Manual device passkey/TLS/LAN/IPv6 checks remain explicit until actually performed.
E6. Run independent security review before deployment; implement critical findings with regression tests. Unverified or missing security properties remain blockers even if nominal tests pass.
E7. Publish reviewed source to this public repository only after secret/content audit. No upstream PRs/forks or service activation without further permission. No release/readiness claim until required acceptance evidence exists.
