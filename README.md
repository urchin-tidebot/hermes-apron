# Hermes Apron

Native [Apron Chat Protocol](https://apron.chat/) integration for [Hermes Agent](https://hermes-agent.nousresearch.com/docs), using [apron-server-go](https://github.com/apron-chat/apron-server-go) as its server foundation.

**Status: implementation underway. Not deployed, audited, or production-ready.**

## Intended deliverables

- Hermes platform plugin with native rooms/threads, mentions/replies, streamed answers, guarded terminal output, uploads, presence/reactions and scheduled delivery, with capability-aware fallbacks.
- Small Go server wrapper/extension for invitation-only, allowlisted passkey accounts.
- LAN-only HTTPS deployment guidance, self-hosted frontend and runtime-only secret injection.
- Reproducible tests and honest acceptance evidence, prioritizing authorization and enrollment safety.

## Specification

- [Requirements and security boundaries](REQUIREMENTS.md)
- [Validation scenarios and release gates](VALIDATION.md)

No real credentials or private deployment configuration belong in this repository. Initial development must not modify the live Hermes gateway, Telegram setup, root system configuration or firewall.

## License

[MIT](LICENSE). Upstream dependencies retain their own licenses; implementation must document provenance and compatibility.
