# Cloudflare tunnel for remote mobile access: applicability record

- Status: not applicable to the documented architecture
- Snapshot: 2026-09-01 at `8eed5c6a0687`
- Type: comparison topic, not a Chipping Orchestrator ADR

Chipping Orchestrator has no local mobile HTTP API to publish and no documented Cloudflare Tunnel integration. Remote
workflow interaction occurs through GitHub's own authenticated service; it is not a tunnel to the orchestrator host.

The optional analytics Postgres database and Streamlit tools are operator-managed observability surfaces. The docs do
not prescribe exposing either through Cloudflare, and neither can control polling workflow state. Any remote exposure
would require operator-supplied authentication, transport, firewall, and data-handling controls.

Sources: [`../../docs/architecture.md`](../../docs/architecture.md),
[`../../docs/observability/analytics-dashboard.md`](../../docs/observability/analytics-dashboard.md), and
[`../../docs/security.md`](../../docs/security.md).

