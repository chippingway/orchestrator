# PostHog applicability and cost controls

PostHog is not part of Chipping Orchestrator's documented stack. There is no PostHog project, ingestion path, replay,
feature-flag client, or vendor cost runbook to configure.

The project does have controls over the resources that can generate local or provider cost:

- global and per-repository parallelism caps bound simultaneous work;
- per-role command specifications, timeouts, retry budgets, and resume limits bound agent attempts;
- `MAX_LINES` and the late size gate stop oversized publication and can split work into explicit children;
- polling cadence, rate-limit handling, and bounded closed-issue sweeps constrain GitHub API traffic;
- analytics retention/pruning bounds the optional Postgres history;
- rotating-file limits bound local logs; and
- detailed trajectory capture is opt-in and disabled by default.

Provider token usage and estimated cost are parsed where available, emitted to local analytics, and summarized in an
issue-visible receipt. The optional analytics database/dashboard can aggregate this data by repository, stage, role,
model, or time period. See [`../docs/observability/usage.md`](../docs/observability/usage.md),
[`../docs/configuration/observability.md`](../docs/configuration/observability.md), and
[`../docs/observability/analytics-dashboard.md`](../docs/observability/analytics-dashboard.md).

These are workload and local-retention controls; they are not a substitute for provider-side spending limits. No
remote product-telemetry budget or billing integration is documented.

