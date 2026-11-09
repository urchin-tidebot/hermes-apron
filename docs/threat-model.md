# Threat model and review

The server and operator OS user are trusted; remote clients, account/display names, room metadata, chat history, message bodies, files and terminal bytes are untrusted. The operator-selected Apron origin is a narrow deliberate network exception, not permission to fetch message-supplied private URLs. A bot with host tools can still access whatever the host grants it: adapter authorization cannot sandbox arbitrary host execution. Keep server state/credentials outside agent artifact/tool workspaces and use a separate OS identity when deploying.

| Boundary | Implemented control | Residual risk / gate |
|---|---|---|
| Network | Explicit loopback only; no autocert, debug or public HTTP listener; HTTPS public URL required for non-test configuration | Proxy/firewall/router/IPv6 isolation not exercised; origin checks do not enforce network isolation |
| Browser | Exact WS/WebAuthn origin and narrow hostname RP; local assets; local-only share/default connection patch; same-origin CSP | Trusted phone TLS/passkeys not run; CSP does not stop a user deliberately navigating an external link |
| Enrollment | 256-bit random invitation, verifier-only storage, max 15 minutes / 256 records; UV WebAuthn; atomic same-store commit | No independent audit or hardware power-loss exercise; trusted host clock required |
| Account access | Immutable allowlist; no guests/open signup/email/external login; explicit owner; bounded human resume | Authenticated active sockets are not forced through a new ceremony on every reconnect; device tokens disabled |
| Revocation | Persistent removal, active sockets closed, upstream sessions/devices/pushes removed; bot credential revoked | Already-issued file/read/live/write capability URLs are separate bearers; see below |
| Hermes | Separate bot, explicit rooms and actor allowlist, structured mentions, echo/edit/reaction suppression; real scoped credential lock | Full model/tool gateway workflow not exercised; tool-side crash effects remain uncertain |
| Content | No configuration from content; no shell execution from commands/embeds; no inbound URL fetching; flat private export | Inbound media ingestion is deferred; raw tool/terminal streaming disabled |
| Secrets | Runtime-only secret files, private state/socket, no HTTP-client capability logging, synthetic canaries, content/history scan | Arbitrary secrets in approved text cannot be guaranteed scrubbed; do not publish unsafe content |
| Resources | Upstream connection/frame/upload/live limits; RPC/queue/recovery/ID caps and deadlines | Upstream chat log has no total byte quota/retention policy; disk exhaustion/operational quotas are a release gate |
| Approval | Administrative slash commands not intercepted; approval text commands blocked; unsupported clarification cancels exact waiter | Safe affirmative approval/clarification not implemented. Native actions remain deferred; blocked for deployment |

## Capability URL treatment

Upstream upload/read/live/write URLs are bearer capabilities. Read URLs need no authenticated socket and can outlive account revocation. Revoking an account cannot retract bytes already copied, read URLs already shared, or an HTTP stream that is already open. Writer capabilities also have their upstream lifetime independent of WS auth. Push is disabled, and the plugin aborts its own live writers when a connection fails. An operator handling a disclosure must remove the affected message/upload and assess copies; do not promise token revocation erases attachments. A stricter per-account HTTP-capability policy is not implemented.

## Local implementation security review

This is a self-review, **not the required independent review**. Findings fixed with observed RED/GREEN regressions:

- Guest-before-registration could not meet closed atomic enrollment: isolated preauth/commit patch.
- Asynchronous persistence acknowledged before durable account/policy state and merely logged failures: synchronous commits, FULL pragma, fail-stop WS/HTTP and restart tests.
- Bot could start adding a human passkey: denied, preventing credential persistence beyond machine rotation.
- Signup metadata still advertised open registration: explicit empty signup list.
- Scalar mention values could be treated as structured authority: strict type checks.
- Corrupt inbox initialization retained its consumer lock: fail-closed cleanup.
- Profile-local locking admitted duplicate consumers in different directories: native Hermes credential reservation with same-process exclusion.
- Refusing a clarification UI left its real open-ended waiter armed: cancel only the exact matching session/request.
- Frontend defaults/share/terminal links could use public Apron infrastructure, and runtime dependencies had reported vulnerabilities: local build mode, CSP, compatible pinned lock update and real browser checks.

Unresolved release blockers include credential removal, safe interactive consent, complete media/tool feature validation, total storage/operational exhaustion controls, crash/power-loss coverage, external low-severity build-tool advisories, independent security review and all approved LAN/device/TLS/recovery drills. No severity is silently converted into a pass.
