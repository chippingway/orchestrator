# Telemetry and local observability

Chipping Orchestrator documents local, operator-controlled observability. It does not document product telemetry, a
remote analytics vendor, an installation identifier, or a usage-reporting control plane.

The authoritative details are in [`../docs/observability.md`](../docs/observability.md),
[`../docs/configuration/observability.md`](../docs/configuration/observability.md), and the focused pages under
[`../docs/observability/`](../docs/observability/).

## Available data surfaces

| Surface | Default | Purpose |
|---|---|---|
| Rotating process log | enabled | operator diagnostics and lifecycle messages |
| Audit JSONL (`EVENT_LOG_PATH`) | optional | structured workflow/security events |
| Analytics JSONL (`ANALYTICS_LOG_PATH`) | enabled under `LOG_DIR` | stage, agent, usage, skill, and outcome analysis |
| Trajectory JSONL (`TRAJECTORY_LOG_PATH`) | off | detailed reasoning/conversation inspection |
| Analytics Postgres | optional replay target | durable query model and materialized rollups |
| Streamlit viewers | operator-started | read-only analytics and trajectory exploration |

All sinks fail open with respect to delivery and are observation-only. Deleting them loses history but does not lose
workflow truth; the polling loop never reads them to choose a transition.

## Data and usage

Analytics records carry identifiers and timing needed to reconstruct runs, stage transitions, agent attempts, token
usage, estimated cost, and skill-trigger evidence. Provider stream output is normalized into a common usage model where
possible. A per-issue usage receipt may also be posted to GitHub.

Trajectory recording is more sensitive: records can contain issue text, source excerpts, prompts, agent responses, and
tool/reasoning detail. It is therefore disabled by default and intended for controlled local use.

## Privacy and retention

Secret-shaped environment variables and GitHub credentials are filtered from child processes, and documented
redaction reduces accidental secret capture. Redaction is not anonymization: issue content, repository names, code,
and agent output can still be sensitive. Operators must protect JSONL files, Postgres, backups, and dashboard access.

Configuration provides file-size/backup limits and analytics retention/pruning controls. Postgres import is explicit
and idempotent; no automatic vendor upload is part of the documented runtime.

## Operational interpretation

These facilities are diagnostics and analytics for the operator, not billing or remotely administered telemetry. No
opt-out variable is required for a remote service because no such service is documented.

