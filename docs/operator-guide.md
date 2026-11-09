# Operator guide — deployment remains gated

Do not run this against the installed gateway, production credentials or LAN while reviewing the project. The commands below are instructions for a separately approved operator run, not evidence that deployment/recovery has been performed. The only services exercised by this implementation are disposable loopback fixtures.

## Build and loopback exercise

Use the provided private TMPDIR and `tools/go build -trimpath -o "$TMPDIR/apron-home" ./cmd/apron-home`. Build the pinned local-only frontend with `tools/frontend`; its last stdout line is the built directory in scratch. `tools/test -q` exercises disposable accounts, operator CLI, real Hermes and Chromium without starting a model.

For an explicit temporary manual experiment, run `serve` with `--state-dir <private-disposable-directory> --listen 127.0.0.1:0 --test-loopback --frontend-dir <built-frontend>`. The printed URL is ephemeral localhost. Interrupt that process when finished; delete its disposable state. Test mode rejects non-loopback, a fixed port, or a production public URL. It must not be used as a LAN exception.

## Future LAN configuration

Choose a stable operator-controlled hostname and arrange local DNS and trusted certificates **before** passkeys. The non-test backend accepts only an exact `https://hostname[:port]` public URL; it uses that exact WS/WebAuthn origin and that hostname as the narrow RP ID. Changing the RP ID strands existing passkeys. Do not add wildcard origins or public Apron origins.

The backend command surface is deliberately small: `serve --state-dir <private-state> --public-url https://chat.example.test --frontend-dir <local-build> --listen 127.0.0.1:8080`. This opens only a loopback HTTP backend. It creates no TLS, firewall, proxy, router, tunnel, gateway or Telegram configuration. No ACME listener or email sender exists in this wrapper.

[examples/lan-proxy.Caddyfile](../examples/lan-proxy.Caddyfile) illustrates a separately approved proxy with explicit IPv4/IPv6 bind addresses, certificate/key **runtime paths**, exact hostname, no automatic HTTP/ACME listener and restricted source ranges. All addresses are reserved documentation ranges and must be replaced; this is not a deployable personal configuration. It has not been activated or used as evidence of isolation. Its privacy choice discards proxy logs; do not enable access/error logs before testing that capability paths are scrubbed.

Caddy reference: [bind](https://caddyserver.com/docs/caddyfile/directives/bind), [remote_ip matchers](https://caddyserver.com/docs/caddyfile/matchers#remote-ip), [explicit TLS files](https://caddyserver.com/docs/caddyfile/directives/tls), [automatic HTTPS controls](https://caddyserver.com/docs/caddyfile/options#auto-https). Proxy source restrictions supplement the host firewall; they do not configure it.

| Layer | Operator responsibility |
|---|---|
| App | Loopback backend, exact public URL/origin/RP, local build, private runtime state |
| TLS proxy | Bind only intended interfaces, trusted chain, HTTPS/WSS/streaming PUT, no request-path credential logging |
| Firewall | Explicit allowed LAN source ranges for BOTH IPv4 and IPv6; deny all other ingress to proxy and backend; account for UDP if enabled |
| Router/network | No WAN forward, public tunnel, public listener, router exception or unintended IPv6 reachability |
| Validation | Intended device succeeds; separate non-LAN IPv4 and IPv6 clients fail; inspect actual listeners/routes; phone TLS/passkeys and recovery drill |

TLS trust, firewall isolation and device UX remain NOT RUN. A config example or successful loopback test proves none of them. Do not put runtime secrets or real environment files in Nix derivations, the Nix store or Git. Runtime credential-file injection is intentional.

## Invitations, ownership and revocation

While the server runs, the local CLI uses `<state-dir>/operator.sock` (0600) inside an owned 0700 directory. A held state lock prevents two wrapper processes from sharing the store. Anyone controlling that OS user/state is an operator, so protect that identity separately from untrusted agent tools.

- `invite --state-dir <state> --ttl-seconds 600 --output <new-private-file>` issues one short-lived account invitation. `--stdout` is a separate intentional one-time display mode; exactly one mode is required. Existing output files are never overwritten. Plaintext is not logged or stored by the service.
- Add `--owner` only when deliberately granting that new account server admin rights. There is no automatic first-owner rule. Display names confer no rights. Later invitations also require the local operator; no bot/server chat command issues them.
- Deliver the file intentionally, paste its token at the **local** `/enroll/` page, and require authenticator user verification. A failed ceremony can restart with the same invitation until expiry. Then sign in to the local Apron frontend with the passkey. Do not send the token through public Apron, message logs or a URL query.
- `revoke-invite --state-dir <state> --id <SHA256-verifier>` cancels unused/pending redemptions. The verifier is SHA-256 of the token bytes, without a trailing newline; it is not a bearer secret.
- `revoke-account --state-dir <state> --id <immutable-account-ID>` removes admission, closes active sockets and forgets that account's upstream session/device/push tokens. It persists across restart. The same command revokes the machine identity `hermes`.

Account IDs shown by the local client are runtime private data. Do not paste a real inventory into repository examples, CI, issues or validation logs. `server.db` contains upstream credentials, so keep the whole state directory private. Do not use a readonly status/config check to provision an account or print a secret.

## Machine identity and Hermes plugin

`machine-secret --output <new-private-runtime-file>` creates a 256-bit credential with 0600 permissions; it prints no secret. Start the wrapper with `--machine-file <file> --rooms <explicit-comma-separated-room-IDs>`. The extension owns a separate fixed `hermes` bot with only role `bot`; it keeps only a credential hash. It uses no person's session. Credentials have a seven-day admission lifetime and revocation is durable; startup with the same file does not refresh that lifetime or undo revocation. Stop/rotate intentionally with a new file when needed. Stop the adapter before replacing its credential file and restart it to acquire the new credential reservation. An in-place change detected on reconnect stops the consumer with `credential_changed` until a controlled restart; it never authenticates the replacement under the old lease. Expiry disconnects every active machine connection and denies queued/new frames and authentication, including after restart; explicit revocation also closes active connections. Human-session expiry still gates resumption, with explicit revocation required to close active human sockets.

Install the Python package into the chosen Hermes environment and enable the repository's platform plugin. Configure that profile's Apron platform `extra` (placement follows the pinned Hermes platform-adapter guide):

```yaml
url: https://chat.example.test
token_file: /run/credentials/apron-plugin/machine
allowed_users: [REPLACE_WITH_IMMUTABLE_ACCOUNT_ID]
rooms: [general]
dm_rooms: []
home_room: general
# artifact_dir: /run/apron-reviewed-artifacts
# terminal_summary: false
```

`APRON_TOKEN_FILE`, `APRON_ALLOWED_USERS` and `APRON_HOME_ROOM` are read with Hermes's profile-scoped helpers. No YAML bearer token is supported. Secrets are read only at connect/send time, not passive validation. A scoped miss does not borrow another profile's environment. Never set `trusted_inbound` or an allow-all chat bypass. The adapter's actor/room policy is always enforced even if a global gateway policy is broader.

Provision rooms/threads with a human account, then restart the server with their immutable IDs and every thread ancestor in `--rooms`. Binding grants only those existing private/public memberships; a bot cannot create rooms, expand scope through public visibility, or accept a human membership grant outside operator scope. Configure the same IDs in adapter `rooms`; the adapter never autojoins outside that policy. Threads are rooms for session and delivery purposes. `dm_rooms` is an explicit operator-selected exception to mention policy, not a guess based on room titles or display names. `!help`, `!status` and `!new` use Hermes's normal handler; leading Apron slash commands stay server commands.

Cron uses the registered standalone sender, `APRON_HOME_ROOM`/`home_room` or an explicit configured room/thread. It creates a separate send-only token connection without taking the consumer lock or rotating the live session. Media in standalone delivery is currently refused rather than silently dropped. `python -m hermes_apron.send --config <private-extra-json> --room <room-ID> --message <text>` exercises the same sender in a separate process. It exits nonzero on failure/uncertain delivery. Do not put secrets in message arguments or configuration JSON.

Artifacts must be owned private regular files directly in a separate private export directory, bounded to 8 MiB. Traversal, symlinks and arbitrary inbound URL fetching are refused. A human must approve a reviewed terminal summary through trusted local integration code; the adapter does not hook arbitrary tool output. Native inline audio/video UX is unverified. Safe affirmative approvals/clarifications are disabled; consent-sensitive work needs another reviewed interface.

## Backup and credential recovery

Before using this with real state, independently review the patch and perform a recovery drill. Stop the wrapper and keep the proxy unavailable; copy the entire owned state directory (SQLite DB plus any WAL/SHM, uploads) to a private encrypted backup outside Git/Nix store. Preserve ownership/modes. Separately back up runtime machine credentials and the proxy trust/certificate material through the operator's approved process. No live backup/restore command is implemented or claimed tested here.

Restore into a private stopped state directory, start loopback only and verify identities, allowlist, invitation consumption/revocation, history, uploads and monotonic IDs before exposing the proxy. An old backup can resurrect revoked accounts/invitations/tokens: reconcile revocations and rotate the machine credential first. Recovery drills with actual backup files/devices remain NOT RUN; automated tests cover server/inbox restart and transaction failure, not a complete operator restore.

Upstream permits additional passkeys (maximum ten), but there is no supported per-credential removal API in the inspected pin. Add a backup passkey on the same trusted origin while you still have access; this wrapper does not add email/guest recovery. A lost or suspected-compromised credential requires revoking the whole immutable account, deliberately enrolling a new account, and separately updating the Hermes actor allowlist/private-room membership after review. Revocation is exercised; selective credential removal and a complete backup/recovery UX are release blockers. Revocation does not erase already-issued media capabilities or copied content.

Push is OFF. Turning on external web-push services/relays would be an explicit egress/privacy decision requiring new code/configuration review. None is necessary for initial LAN use.
