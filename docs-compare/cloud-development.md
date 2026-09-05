# Cloud development applicability

Chipping Orchestrator does not document a hosted control plane, hosted execution service, tenant model, or private
Cloud API. The product process runs on an operator-controlled host and coordinates local worktrees and local Codex or
Claude CLIs against GitHub repositories.

Remote services in the documented topology are narrower:

- GitHub supplies issues, labels, comments, refs, pull requests, reviews, and checks;
- configured repositories may be remote and private when the operator's token permits access; and
- the optional analytics Postgres database may be operator-hosted elsewhere, but remains an observation-only sink.

Workflow state remains in GitHub. Candidate source and agent execution remain on the machine running the orchestrator.
No request routing, authentication protocol, tenancy boundary, generated client, or remote executor contract is
specified for turning this into a hosted service.

This is an applicability statement for the snapshot, not a roadmap claim. The current boundaries are described in
[`../docs/architecture.md`](../docs/architecture.md), [`../docs/security.md`](../docs/security.md), and
[`../docs/observability/analytics-database.md`](../docs/observability/analytics-database.md).

