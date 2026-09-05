# Cloud shared-contract applicability

There is no documented public/private Cloud split or Cloud-refactor contract in Chipping Orchestrator. The repository
does not expose a hosted execution API, generated Cloud client, product UI package, or shared wire schema between local
and hosted implementations.

The reusable boundaries that do exist are local Python contracts:

- immutable configuration and per-repository specifications;
- GitHub client operations and workflow handlers;
- agent-backend command/result normalization;
- worktree and hardened git/push helpers; and
- observation-only JSONL/Postgres record schemas.

These boundaries support the polling application and its operator tools; they are not presented as a public SDK or
Cloud compatibility surface. Any future remote execution/control interface would need an explicit security model,
durable ownership rules, API schema, and migration plan rather than being inferred from the current package layout.

See [`../docs/architecture.md`](../docs/architecture.md),
[`../docs/architecture/platform-modules.md`](../docs/architecture/platform-modules.md), and
[`../docs/architecture/workflow-modules.md`](../docs/architecture/workflow-modules.md).

