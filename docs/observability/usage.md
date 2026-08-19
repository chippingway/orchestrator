# Usage parser

Pure-Python helpers that decode the JSONL stdout `agents.AgentResult` carries into a `UsageMetrics` dataclass —
backend, distinct model(s), turn count, input / output / cached / cache-read / cache-write token totals, `cost_usd`, and
a `cost_source` tag of `reported` / `estimated` / `unknown-price` / `no-usage`. No external dependency: the parser is
jq-free.

The pass runs once the audit `agent_exit` event has already fired, and `record_agent_exit` writes what it returns as
the token / cost detail on the analytics [`agent_exit` record](event-streams.md#agent_exit-records) and the
`run_usage` summary on the [trajectory record](trajectories.md#trajectory-sink-trajectory_log_path). Two siblings ride
the same stream under the same resilience contract: the opt-in skill-trigger extractor and the trajectory classifier
below. None of the three reads or writes a file — redaction, truncation, and the append itself belong to the writers
downstream of them.

Which module owns which piece is in [`architecture.md`](../architecture.md#top-level-layout), the single place that
inventory is maintained; the knobs are in [`configuration/observability.md`](../configuration/observability.md).

**Module layout.** The package initializer is the public surface: under a narrow `__all__` it re-exports the nine
parsers `metrics.py`, `skills.py`, and `trajectory.py` define, a per-backend trio each, plus the five result types they
hand back — `UsageMetrics` and `SkillTriggers` from the first two, and `AgentTrajectory` / `TrajectoryStep` /
`TurnUsage` from `trajectory_models.py`. Provider payload handling is split behind them: `protocol.py` holds the JSONL
vocabulary and `event_stream.py` the resilient line decoder, `prices.py` the first-party price tables and
`model_names.py` the nested model-name lookup, `claude_rows.py` / `claude_summary.py` and `codex_rows.py` /
`codex_summary.py` the per-provider frame decoding and run summary, `shell_segments.py` / `skill_commands.py` /
`skills_claude.py` / `skills_codex.py` the skill-evidence classification, and `trajectory_claude_blocks.py` /
`trajectory_claude_stream.py` / `trajectory_claude_turns.py` plus `trajectory_codex.py` the timeline reconstruction. The
trajectory classifier reuses the same event decoder, pricing path, and skill evidence owners, so the resilience and
cost-precedence contracts are defined once. Each published name is bound once at import to its owner's own object, and a
binding does not follow a later patch, so a test intercepting a parser targets the module its caller imported — every
live caller names the owner it is typed by, and no flat module sits beside the package to resolve one through.

**Two parsers, one dispatcher.** `parse_claude_usage(stdout)` consumes claude `--output-format stream-json` events,
groups assistant frames by `message.id` so the final-frame usage wins (claude streams partial counts on intermediate
frames), and sums per-model. `parse_codex_usage(stdout, fallback_model=None)` consumes codex `--json` events and treats
usage as cumulative across the session: the *last* non-zero usage record is the authoritative total.
`parse_agent_usage(backend, stdout, fallback_model=None)` dispatches by backend string the same way `agents.run_agent`
does.

**Cost precedence.** A `total_cost_usd` reported by the CLI itself always wins (`cost_source="reported"`); otherwise the
parser walks first-party Anthropic / OpenAI price tables baked into the module and produces an estimate (`"estimated"`).
When usage is present but the model SKU does not match any priced family, the parser returns
`cost_source="unknown-price"` and `cost_usd=None` rather than guess at zero or bill cached tokens at the input rate. An
empty stream — or one with no usage frames at all — yields `"no-usage"`.

**Resilience.** Malformed JSON lines (banner text, truncated frames, partial flushes) are silently skipped so a single
bad line never invalidates the rest of the stream. `_run_agent_tracked` (in `workflow/engine/usage.py`) calls
`parse_agent_usage` after every tracked agent run and appends the parsed counts to the
[analytics sink](event-streams.md#analytics-sink-analytics_log_path) under `event="agent_exit"`; a
parser exception is caught and downgraded to a `log.exception`.

**Terminal verdict surface.** Beyond the analytics sink, `_accumulate_issue_usage` (in `workflow/engine/usage.py`,
beside `_run_agent_tracked`) folds each run's
`UsageMetrics` into per-issue counters on the pinned state (`issue_agent_runs` / `issue_total_tokens` /
`issue_total_cost_usd` / `issue_cost_sources`; see [state-machine/labels-and-state.md][pinned-state]). When an
issue reaches a terminal, `_format_issue_usage_verdict` renders those counters into one visible receipt line
posted on the issue thread — `:receipt: this issue: N agent runs · T tokens · $X.XX`, with `(est.)` appended when any
run's cost was `estimated` and the figure collapsed to `unknown` when an `unknown-price` run leaves the total
incomplete. The PR merged / rejected finalizers and the closed-`question` terminal post it as a standalone tracked
comment; the `umbrella` close comment appends it. It is a read-only summary — nothing gates on the figure — and it is
skipped when no run was ever counted.

**Skill-trigger extractor (opt-in).** A sibling trio mirrors the usage parsers' two-parsers-one-dispatcher shape and
resilience contract to record which agent *skills* a run loaded, gated behind `TRACK_SKILL_TRIGGERS` (default off;
see [`agent_exit` records](event-streams.md#agent_exit-records)). The result is a names-only
evidence model on `SkillTriggers`: `triggered` / `trigger_counts` are the loaded skills, `evidence` maps each to its
tier (`confirmed` / `inferred`), and `incidental` / `incidental_counts` are path-only references that never become
loads. The two buckets are independent —
a skill both read and inspected is recorded in both — the only exclusion is structural: an incidental reference never
enters `triggered` / `trigger_counts` or the `skill_triggered` audit events. `parse_claude_skills(stdout)` reads the
firm **confirmed** signal — `tool_use`
content blocks named `Skill` in the `assistant` stream — and returns `input.skill` in first-seen order, de-duplicating
per invocation by the block `id`. (A captured real stream showed that under `--include-partial-messages` each completed
content block lands in its own `assistant` frame — the content array is partitioned across frames, not a cumulative
snapshot that repeats earlier blocks the way the `usage` sub-object does — so the parser walks every frame and de-dups
by `id` rather than keeping the last frame per message id.) Claude has no dedicated file mechanism, so it produces no
incidental references. `parse_codex_skills(stdout)` recognizes the codex shape: codex has no dedicated `Skill` tool, so
its file-based skill mechanism surfaces only as a `command_execution` item whose shell `command` opens a skill's
`skills/<name>/SKILL.md` file (codex's own "open its SKILL.md" instruction). A captured reviewer run pinned this — codex
both registered-under-`$CODEX_HOME/skills/` and project-local `.agents/skills/` reads match. The command is first
unwrapped (peeling the `bash -lc "…"` shell) and split into sub-commands on **unquoted, unescaped** operators —
quote- and backslash-aware, so a metacharacter inside a quoted argument (`rg 'foo|bar' path`) or a backslash-escaped one
(`rg foo\|cat path`) does not fabricate a spurious segment — then each `SKILL.md` match is routed by its sub-command's
leading verb (skipping any `NAME=value` env prefix). Only a verb
established as a **direct reader** (`cat` / `sed` / `head` / …) makes the reference an **inferred** load; every other
verb — an inspection / search (`git diff` / `git status` / `rg`), an env-prefixed inspection (`GIT_PAGER=cat git
diff …`), or a generic path-only command (`echo …`) — makes it an **incidental** reference. Even a reader verb is
demoted to incidental when the `SKILL.md` is *written* rather than read: an output-redirect target
(`cat t > .agents/skills/x/SKILL.md`) or a non-reading mode (`sed -i` / `--in-place`) is an incidental reference, so a
skill file a run only writes is never miscounted as a load. So a read chained after an inspection still counts, and a
bystander `git diff` over a changed SKILL.md does not fabricate a load. Started/completed
echo the same command, so the parser dedups by the shared `item.id` (last-frame-wins, as for usage) — for inferred
loads and incidental references alike. It reads only the `<name>` path segment and the routing verb — never the command
text or its `aggregated_output` (the file's contents), both of which can echo user content (names-only Privacy). The
inferred signal stays **heuristic** within the reader allowlist: a reader that opens a SKILL.md for an unrelated reason
would still register as an inferred load, while defaulting non-readers to incidental keeps an unrecognized command from
fabricating a trigger. `parse_agent_skills(backend, stdout)` dispatches by backend exactly as `parse_agent_usage` does.
The offered-skills set (`SkillTriggers.available`) is
**confirmed on claude** — read from the dedicated `skills` array in the `system`/`init` frame, captured against a real
stream — and
stays **empty on codex** at the parser layer: a captured `codex exec --json` stream (v0.142.5) carries no offered-skills
frame at all, so `record_agent_exit` backfills the codex offered set out-of-band from the filesystem via
`skills.discovery.discover_local_skills(cwd)` instead. The *triggered* set does not
depend on it either way. As with the usage parsers, malformed JSONL lines are skipped and a missing / renamed field
yields an empty result rather than an exception. Only the skill *name* is ever read — never the `Skill` tool's `args`
(Privacy).

**Trajectory classifier.** A third sibling trio mirrors the same two-parsers-one-dispatcher shape and resilience
contract to reconstruct a run's *trajectory* — the ordered timeline of tool calls / results interleaved with the
assistant / user text turns — into an `AgentTrajectory` dataclass: `backend`, a best-effort `system_prompt` / `tools`,
the names-only `skills` (`SkillTriggers`), an ordered `steps` tuple of `TrajectoryStep` (`kind` is `"tool_call"` /
`"tool_result"` / `"assistant_message"` / `"user_message"`, with `name` / `tool_id` / raw `content` — `name` /
`tool_id` empty on the text turns — plus a `turn` index tying each billed step back to the assistant turn that
produced it), `final_output`, and a best-effort `turns` tuple of per-turn token usage (`TurnUsage`, parallel to `tools`
/ `skills` and claude-only today). `parse_claude_trajectory(stdout)` reads the offered tools from the `system`/`init`
frame's `tools` array, then the ordered timeline: assistant `text` blocks become `assistant_message` turns and
`tool_use` blocks `tool_call` steps; user `text` blocks become `user_message` turns and `tool_result` blocks
`tool_result` steps — calls / results joined by `tool_use_id` and de-duplicated per id the same way
`parse_claude_skills` is, while id-less text blocks ride claude's per-completed-block framing — and the final answer
from the `result` frame's `result` string. It also groups those assistant frames by `message.id` in first-seen order to
assign each a 0-based `turn` index — stamped onto the `assistant_message` / `tool_call` steps that frame produced (a
`tool_result` / `user_message` step is a turn *input*, not billed output, so its `turn` stays `None`) — and emits one
`TurnUsage` per turn: `model`, `input_tokens` / `output_tokens`, `cache_read_tokens` / `cache_write_tokens` (the 5m + 1h
cache-creation buckets summed), and an always-*estimated* `cost_usd` / `cost_source` (`"estimated"`, or
`"unknown-price"` with `cost_usd=None` for an unpriced SKU — a reported `total_cost_usd` is a run-level figure and
never reaches a turn). The per-turn estimate reuses the same `claude_estimate_cost` price path on
`observability/usage/prices.py` as the run aggregate, so the per-turn figures stay in lock-step with
`parse_claude_usage`'s run totals. `parse_codex_trajectory(stdout)` treats each
`command_execution` item as one call (its `command`) plus one result (its `aggregated_output`) and each `agent_message`
item as one `assistant_message` turn (its `text`), collapsing each item's started/completed pair by the shared
`item.id`, and reads the final answer from the last `agent_message` `text`; it leaves `turns` empty with every
`step.turn` `None`, since codex usage frames are cumulative across the session rather than per-turn. Both reuse the
matching skill extractor for the `skills` field. `parse_agent_trajectory(backend, stdout)` dispatches by backend exactly
as the usage / skill dispatchers do. `system_prompt` stays `None` and `tools` stays empty in the classifier whenever a
backend's stream does not expose them (codex exposes neither); the analytics writer backfills codex `tools` out-of-band
from `skills.discovery.discover_codex_tools()`. Malformed JSONL lines are skipped and a missing / renamed field
yields an empty section rather than an exception. Unlike the skill extractor, this classifier records the **raw** stream
payload — tool inputs, tool outputs, and the final text — verbatim: it deliberately does **not** redact, truncate,
or write any file. Those concerns belong to its downstream writer,
`observability/analytics/trajectories/`'s `persistence.maybe_record_trajectory`
(called from `record_agent_exit`), which redacts every free-text field, applies the head/tail and total-record
truncation caps, and appends the `agent_trajectory` record to the
[trajectory sink](trajectories.md#trajectory-sink-trajectory_log_path) — only when
`TRAJECTORY_LOG_PATH` is enabled and always behind its own fail-open guard.

[pinned-state]: ../state-machine/labels-and-state.md#pinned-state
