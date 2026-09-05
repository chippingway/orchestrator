# Unauthenticated identity probe: applicability record

- Status: not applicable to the documented architecture
- Snapshot: 2026-09-01 at `8eed5c6a0687`
- Type: comparison topic, not a Chipping Orchestrator ADR

Because Chipping Orchestrator exposes no LAN application API or mobile pairing flow, it has no unauthenticated identity
endpoint, host id, mobile contract version, password lockout, or route exemption. Repository identity is configured as a
GitHub slug and validated through authenticated GitHub operations rather than through local network discovery.

This record does not authorize an identity endpoint. Any future unauthenticated route would require a complete threat
model and an explicit network-interface decision.

Sources: [`../../docs/configuration.md`](../../docs/configuration.md) and
[`../../docs/security.md`](../../docs/security.md).

