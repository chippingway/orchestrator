# LAN listener for mobile: applicability record

- Status: not applicable to the documented architecture
- Snapshot: 2026-09-01 at `8eed5c6a0687`
- Type: comparison topic, not a Chipping Orchestrator ADR

Chipping Orchestrator has no HTTP application listener, desktop supervisor, or mobile client. Its workflow interface is
GitHub, while local operator interfaces are the process console and optional Streamlit viewers. It therefore makes no
loopback-versus-LAN binding decision and exposes no bearer-authenticated mobile API.

The process does make outbound HTTPS calls to GitHub and may connect to an operator-configured Postgres service. Those
client connections are not inbound product listeners. Streamlit deployment and access control remain an operator
responsibility and are not described as a mobile control plane.

Adding any network-facing control listener would introduce a new authentication, authorization, secret-storage, and
host-boundary decision requiring its own design and security review. Nothing in this record grants that listener.

Sources: [`../../docs/architecture.md`](../../docs/architecture.md) and
[`../../docs/security.md`](../../docs/security.md).

