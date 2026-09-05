# Distribution and launcher applicability

Chipping Orchestrator does not use AO's desktop bootstrapper, Electron updater, or legacy npm launcher. There is no
documented npm package, `ao start` compatibility path, desktop release channel, or application state file.

The documented distribution shape is Python-native:

- dependencies and locks are managed with `uv` and `pyproject.toml`;
- `uv build` produces the package artifacts;
- the installed console script is `chipping-orchestrator`;
- `python -m orchestrator` is the equivalent module entry point;
- `./run.sh` is the production-oriented self-update/restart wrapper; and
- an optional systemd user unit can supervise the process.

The installed-CLI smoke test verifies the console entry point from an isolated built wheel. Runtime self-update in
`run.sh` follows the configured git checkout; it is not an application binary auto-update service. See
[`../README.md`](../README.md), [`../docs/configuration/operations.md`](../docs/configuration/operations.md), and
[`../docs/architecture.md`](../docs/architecture.md).

