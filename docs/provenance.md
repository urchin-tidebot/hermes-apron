# Provenance, compatibility and licenses

Inspected public upstream sources on 2026-11-09; actual APIs and wire exchanges, not documentation examples alone. No upstream fork or publication was created. `tools/prepare.py` fetches exact commits, verifies HEAD and applies hash-keyed isolated patches in the provided TMPDIR. Go sums, uv.lock, frontend lock patch and flake.lock record dependency resolution. Runtime credentials are never build inputs.

| Component | Exact source / version | License / exercised scope |
|---|---|---|
| Go server foundation | [cefba0193cf5cf8407dfb47c0970b9a26e6c1b8c](https://github.com/apron-chat/apron-server-go/tree/cefba0193cf5cf8407dfb47c0970b9a26e6c1b8c), Go pseudo-version `v0.0.0-20261108143803-cefba0193cf5` | MIT, Copyright 2026 apron-chat; real apron/aproncmd/store, wrapper and upstream race tests |
| Hermes | [6cff782b8d081a0ed382eaf75c432d452cd452cc](https://github.com/NousResearch/hermes-agent/tree/6cff782b8d081a0ed382eaf75c432d452cd452cc) | MIT, Copyright 2025 Nous Research; actual plugin loader/context/registry, profile helpers, BasePlatformAdapter, clarify waiter and credential lock APIs; no model calls |
| Frontend | [95a6314e2629f0965dd61fa688f7eb1b4abbd26c](https://github.com/apron-chat/apron-web/tree/95a6314e2629f0965dd61fa688f7eb1b4abbd26c) | MIT, Copyright 2026 apron-chat; the server's exact paired submodule, patched lock/local-only mode, full tests/build and Chromium login/chat |
| Wire fixtures/schema | [6ac69cc170c172ba470ebb619c1042eaf722a1a6](https://github.com/shazow/apron/tree/6ac69cc170c172ba470ebb619c1042eaf722a1a6), 2026-11-04 | Protocol CC0-1.0; real submodule used by server/frontend tests |
| Live protocol inspection | [apron.chat/protocol.md](https://apron.chat/protocol.md), front matter v10, updated 2026-10-30 | CC0-1.0; fetched SHA-256 `c5d74dd956e8dce9f6fe62eb7022a219e0c668be1bc1f536af39fc2e7f44f1d4` |
| Go compiler | `go1.27.3` pinned in tooling/workspace/CI | Go BSD-3-Clause; upstream minimum is 1.27.0. Initial tests used 1.27.0/1.27.3; audit identified standard-library advisories in 1.27.0, so final builds use 1.27.3 |
| WebAuthn | `github.com/go-webauthn/webauthn v0.18.2` | BSD-3-Clause; actual registration/assertion verifier, never replaced by project cryptography |
| WebSocket | `github.com/coder/websocket v1.8.14` | ISC; actual Go sockets |
| SQLite | `modernc.org/sqlite v1.59.0` | BSD-3-Clause port, SQLite public-domain upstream; actual persistent transactions/restarts; FULL synchronous override |
| CBOR | `github.com/fxamacker/cbor/v2 v2.9.4` | MIT; upstream/proof fixtures |
| Python transport | `websockets 16.0` | BSD-3-Clause; remaining runtime uses stdlib; dependency and hashes pinned in uv.lock |
| Test/browser/lint tools | pytest 9.1.1, pytest-asyncio 1.4.0, Playwright 1.64.1, uv 0.13.0; dev Ruff 0.15.22 | MIT / Apache-2.0 as supplied upstream. Nix Ruff 0.15.14 was also exercised. Chromium is supplied by the environment, not vendored |
| Nix tools | nixpkgs `f4a03c008967841f2a0b3cb7c436fc6fc31671f6` | Package-specific licenses; exact narHash in flake.lock; no runtime secret inputs or host configuration |

The server's SERVER.md references protocol commit f97f59e in prose, while its actual gitlink pins 6ac69cc. Compatibility is established against actual code and pinned fixtures plus real wire tests. Public frontend HEAD 779be1a40fa27264bbbd4d5b774610dcad077878 was inspected; the paired 95a6314 pin was selected for reproducible compatibility. Other versions are untested.

## Documented deviations from upstream defaults

The closed-enrollment patch adds an explicit extension API and runner config accessor, invitation preauth state, same-store policy transaction, synchronous fail-stop persistence, FULL SQLite commits, bounded absolute human token resumption, machine token auth, bot/passkey separation, disabled device-token creation and no advertised open signup. It preserves WebAuthn validation and normal server authorization. See [patch rationale](../patches/README.md).

Security audit also requires dependency resolution above the upstream module minimums: `golang.org/x/net v0.62.0` and `golang.org/x/crypto v0.58.1-0.20261009181718-2f1f834330b2` (official reviewed fix commit), with the resulting transitive pins in go.mod/go.sum. These override the workspace graph for both wrapper and upstream tests; they do not change the pinned server source commit. The initial audit's standard-library and module findings are recorded, not silently omitted.

The frontend patch updates compatible dependency ranges in the lockfile to remove reported runtime vulnerabilities and adds `VITE_LOCAL_ONLY=1`: same-origin default socket/share links and no external terminal viewer. The build script always selects that mode and copies frontend/font licenses into the static build. Five low-severity development-tool findings remain; runtime `npm audit --omit=dev` reported zero. No automatic audit fix or major dependency upgrade was applied.

## Distribution notices

Source remains MIT; upstream licenses are not replaced. `tools/build` includes each actual runtime Go module's LICENSE/COPYING/NOTICE files and a path-free index with the binary in scratch. Keep that directory when distributing a reviewed binary. Source tests adapted from upstream WebAuthn software-authenticator tests carry explicit MIT attribution. The fetched server's license is retained in the materialized tree; no full server copy is in this repository.

The local frontend retains Apron's MIT notice and the bundled Nunito/Recursive font SIL Open Font License texts in `build/licenses`. Its npm dependencies retain their own notices (including DOMPurify Apache-2.0/MPL-2.0 and Markdown-it MIT); a reviewed redistribution must retain all required bundle/dependency notices. A complete independent transitive license compliance review remains a publication gate, not a claimed automated pass.

Python wheels retain upstream dependency notices through normal package installation; this project's wheel contains its own MIT license. No Hermes core files or production configuration are bundled. CI action commits are pinned and use Node 24; remote CI itself has not run in this implementation session.
