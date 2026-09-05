# Process environment and child isolation

Chipping Orchestrator has no GUI-launched HTTP daemon or login-shell environment bridge. Its long-lived process starts
from a shell, the `run.sh` wrapper, or an optional systemd user service, then launches transient Codex, Claude, verify,
git, and support subprocesses.

This page summarizes [`../docs/configuration.md`](../docs/configuration.md),
[`../docs/configuration/operations.md`](../docs/configuration/operations.md), and
[`../docs/security.md`](../docs/security.md).

## Startup environment

Configuration comes from process variables plus a repository-root `.env` file read at startup. Multi-repository values
are parsed into immutable configuration objects before polling begins. An operator changes configuration by editing the
environment and restarting the process/service; there is no live daemon settings API.

GitHub credentials are deliberately excluded from repository `.env`. `GITHUB_TOKEN` may be supplied by the parent
environment, and `GITHUB_TOKEN_FILE` may point to a protected file outside the repository. `run.sh` and the systemd
example support this separation.

## Child-process policy

The orchestrator builds explicit child environments rather than blindly forwarding every secret:

- agent subprocesses lose GitHub credentials and production-secret-shaped variables;
- provider authentication needed by the selected Codex or Claude CLI is retained through an allowlist;
- local verification commands also lose provider credentials because they do not need agent access;
- orchestrator-controlled git identity can be injected independently of the host's global config; and
- authenticated push receives credentials only through a temporary askpass boundary.

Filtering is defense in depth, not the sandbox. Agents run with provider sandbox/approval bypass flags, so the host OS
account, container, or VM must supply the actual containment boundary.

## Lifecycle

Agent and verification commands run in their own process groups. Timeout, SIGINT, SIGTERM, and bounded shutdown target
the group so descendants do not survive the orchestrator. The systemd example uses restart policy and environment-file
configuration; `run.sh` can self-update the orchestrator and restart when its own package changes.

## Non-applicable desktop concerns

There is no Electron parent process, desktop `PATH` repair, persisted daemon environment snapshot, or distinction
between GUI and shell launch environments in the documented architecture.

