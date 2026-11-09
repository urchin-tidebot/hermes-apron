# Implementation status

Work in progress; not deployed or production ready. The initial acceptance documents remain authoritative.

| Boundary | Current evidence |
|---|---|
| Fresh closed admission | Real Go server test passes; supported empty allowlist, no guests/email/external auth |
| Atomic enrollment | Under investigation: upstream requires guest registration and asynchronous persistence logs failures |
| LAN/TLS/phone/IPv6 | NOT RUN; separate operator gate |
| Independent security review | NOT RUN; release blocker |

Upstream is pinned in go.mod to cefba0193cf5cf8407dfb47c0970b9a26e6c1b8c (MIT).
