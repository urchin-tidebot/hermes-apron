# Hermes × Apron

An exercised, invitation-only [Apron v10](https://apron.chat/protocol.md) server wrapper and separately installable [Hermes](https://hermes-agent.nousresearch.com/docs/developer-guide/adding-platform-adapters) platform plugin. MIT. **Development implementation; not deployed or ready for production.**

Closed passkey enrollment uses the real pinned Go server and WebAuthn library, an immutable account allowlist, and one SQLite transaction for the verified account, credential, admission and invitation consumption. A small isolated upstream patch closes API/persistence gaps; the server tree is fetched into scratch, never copied into this repository. No guests, open signup, email, external login, unbounded device tokens or default human administrator.

The real Hermes adapter supports native Markdown/replies, explicit rooms and threads as rooms, persistent RPC/heartbeat/reconnect, durable recovery and dispatch deduplication, append streams, bounded artifact uploads, typing, and standalone scheduled delivery. A separate runtime credential identifies a non-admin bot. Reviewed terminal summaries are opt-in; arbitrary tool output is never hooked automatically. Interactive approvals and clarifications remain blocked; see the matrix before using this for work.

## Python-native experiment

The `experiment/python-native` branch explores an original Python Apron server
library hosted directly by Hermes, with no Go runtime dependency. Its new
[requirements](docs/python-native/REQUIREMENTS.md) and
[validation contract](docs/python-native/VALIDATION.md) supersede the Go-specific
architecture for that experiment, not the existing security requirements.
The tested Go implementation is preserved at `reference/go-server-validated`.
No Python-server implementation or validation is claimed merely by this specification.

## Run the checks

Use a short private `TMPDIR`; deep paths can exceed the operating system's Unix
socket pathname limit during fixture startup. For example, after creating
`$HOME/.hermes/cache/scratch` with mode 0700, run
`env TMPDIR="$HOME/.hermes/cache/scratch" nix develop --command make check`.
Use a command prefix rather than changing the persistent shell environment.
No global packages or service configuration are changed.

```sh
nix develop                 # optional pinned development shell
make check                  # Go race tests, real upstream tests, Python/browser/plugin tests, lint/build/audit
make frontend               # full patched upstream frontend tests/check/build/runtime audit
nix flake check             # offline source checks once Nix dependencies are available
```

`tools/test -q` uses a lockfile venv and fresh pinned public Hermes sources in `TMPDIR`, sanitizes inherited environment variables, builds the wrapper, runs disposable loopback services and closes them. Chromium is required; on NixOS the scripts use system Node and a contextual libstdc++ for Playwright. `tools/go` is required for the patched Go workspace; unwrapped Go commands do not select the patch. First use fetches public dependencies. No model calls are needed.

## Review and operate

- [Implementation and security matrix](docs/implementation-status.md)
- [Exact execution evidence and RED/GREEN ledger](docs/validation-results.md)
- [Architecture and crash guarantees](docs/architecture.md)
- [Threat model and security review](docs/threat-model.md)
- [Setup, backup, revocation and recovery](docs/operator-guide.md)
- [Upstream compatibility, pins and licenses](docs/provenance.md)
- [Patch rationale](patches/README.md)
- Original [requirements](REQUIREMENTS.md) and [acceptance scenarios](VALIDATION.md)

The application listens only on explicit loopback addresses. Its HTTP test exception requires an ephemeral loopback port and excludes a production public URL. LAN HTTPS, phone/browser trust, IPv4/IPv6 ingress, backup/recovery drills and a complete independent audit are separate deployment gates. Focused independent review of the corrected security findings passed; this does not establish production readiness. Nothing here activates a proxy, firewall, gateway, Telegram integration or LAN service.

## Plugin installation

Install this package into the chosen Hermes environment with `uv pip install --python <that-venv>/bin/python .`, then place/symlink this checkout as a user platform plugin and explicitly enable it using Hermes's plugin commands. Do not install into a global environment. The checkout's `plugin.yaml` and `__init__.py` are the loader entry point. Configure only that profile, using the `extra` fields in the [operator guide](docs/operator-guide.md). No installed Hermes files are patched.

## License

[MIT](LICENSE). Upstream code, libraries, browser assets and fonts retain their licenses; see [provenance](docs/provenance.md). Development source has passed parent publication checks; release artifacts and deployment still require separate review.
