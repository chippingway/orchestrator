# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The prompt one late adjudication is spawned with, and only that one.

Built beside its single caller rather than with the shared builders, the way
the drift-resume prompt is: nothing else asks this question. It opens on the
same header every conversation-carrying prompt does -- the issue body, the
trust-filtered thread, the tracked-repository block -- so an untrusted author's
comment is as absent here as it is from the implement and decompose prompts.

What it adds is everything the late question needs and the initial one never
had: that committed work ALREADY exists and is not to be rewritten, the
declared scope this generation owns, the two frozen commits the diff is to be
read between, the measurement that brought the candidate here, and where the
issue sits in its lineage.

The diff it names is the three-dot one, because that is the range the
measurement was taken over. Two dots would show everything that happened on
the base since the candidate branched as well, so on a diverged history the
agent would be adjudicating changes nobody measured -- and deciding a split
over work this candidate does not add.

Three numbers in it are read back off the owners that enforce them rather than
typed in, for the reason the child cap already is: a bound an agent is told and
a bound it is judged against must be one number. The child cap comes from the
split validator, the lineage bound from the record whose invariant it is, and
the category vocabulary from the closed set a verdict is recorded under -- so a
category widened in review reaches the prompt with it, and one an agent
invents still records as `unknown`.

The false positives are named out loud because the gate is a size gate and
size is not the question. A diff dominated by legitimate generated or data
artifacts is a small change with a large diff and gets a fast `single`; the
same artifacts looking like something nobody should have committed are a
question for a human, not a verdict for an agent. Saying both in the prompt is
what keeps the first from being split and the second from being waved through.
"""
from __future__ import annotations

from github.Issue import Issue

from orchestrator import config
from orchestrator.workflow.engine import comments as _comments
from orchestrator.workflow.engine.comments import _SECTION_SEP
from orchestrator.workflow.late_split.events import LateVerdictCategory
from orchestrator.workflow.late_split.models import (
    MAX_LINEAGE_DEPTH,
    LateGeneration,
)
from orchestrator.workflow.stages.decomposition.validation import _MAX_CHILDREN

_NO_BODY = "(no body)"

_NO_PRIOR_COMMENTS = "(no prior comments)"

_WHOLE_ISSUE = "(the whole issue)"

# The categories an adjudication may name, read off the closed vocabulary a
# verdict is recorded under. `UNKNOWN` is not offered: it is what this binary
# answers for a spelling it does not know, not one an agent may choose.
_CATEGORIES = ", ".join(
    f"`{member}`"
    for member in LateVerdictCategory
    if member != LateVerdictCategory.UNKNOWN
)

_MAY_SPLIT = (
    "- a child of this issue would be born at depth {depth}, which is still "
    "inside the bound, so `split` is available to you."
)

_NO_SPLIT = (
    "- this issue may NOT split further, so `split` is not available to you: "
    "an oversized change here resolves as `single` or asks a human with "
    '`"category": "lineage_bound"`. Do not propose children.'
)

_UNKNOWN_DEPTH = "unknown"


def _build_late_decompose_prompt(
    spec: config.RepoSpec,
    issue: Issue,
    comments_text: str,
    generation: LateGeneration,
    specs: list[config.RepoSpec],
) -> str:
    """Compose the late adjudication prompt for one frozen candidate."""
    body = issue.body or _NO_BODY
    convo = comments_text or _NO_PRIOR_COMMENTS
    tracked = _comments._build_tracked_repos_context(spec, specs)
    tracked_block = f"{tracked}\n\n" if tracked else ""
    header = (
        f"You are the late decomposer for GitHub issue #{issue.number}: "
        f"{issue.title!r}.\n\n"
        f"Issue body:\n{body}\n\n"
        f"Conversation so far:\n{convo}\n\n"
        f"{tracked_block}"
    )
    return _SECTION_SEP.join((
        header + _candidate_block(generation),
        _lineage_block(generation),
        _outcome_rules(),
    ))


def _candidate_block(generation: LateGeneration) -> str:
    """What already exists, what it measured, and how to read it."""
    scope = generation.scope or _WHOLE_ISSUE
    return (
        "A developer has ALREADY implemented this issue in the current "
        "working directory and COMMITTED the work. Nothing has been pushed "
        "and no pull request carries it. The orchestrator measured the "
        "prospective pull-request diff and it is larger than this repository "
        "lets one change be, so you are deciding what happens to work that "
        "already exists. You are NOT implementing anything and NOT reviewing "
        "it.\n\n"
        "Declared scope of this attempt:\n"
        f"{scope}\n\n"
        "The frozen candidate:\n"
        f"- candidate commit: {generation.candidate_sha}\n"
        f"- base commit: {generation.base_sha}\n"
        f"- measured additions: {generation.additions} lines, against a "
        f"ceiling of {generation.threshold}\n\n"
        "Read the exact diff with "
        f"`git diff {generation.base_sha}...{generation.candidate_sha}` in "
        "the current working directory -- `--stat` and `--numstat` for its "
        "shape, a path argument for one part of it. THREE dots, not two: "
        "that is the prospective pull-request range, the one the measurement "
        "above was taken over, and it shows what this candidate ADDS rather "
        "than everything that has happened on the base since. Those two "
        "commits are frozen: they are what every later step acts on, so "
        "decide from them and never from `HEAD`, the branch, or the working "
        "tree. You MUST NOT commit, push, fetch, or modify any file -- you "
        "are read-only."
    )


def _lineage_block(generation: LateGeneration) -> str:
    """Where this issue sits in its lineage, and what that permits."""
    depth = generation.lineage_depth
    shown = _UNKNOWN_DEPTH if depth is None else depth
    if generation.may_split:
        rule = _MAY_SPLIT.format(depth=depth + 1)
    else:
        rule = _NO_SPLIT
    return (
        "Lineage:\n"
        f"- root issue: #{generation.root_issue}\n"
        f"- this issue: #{generation.current_issue}\n"
        f"- lineage depth: {shown} of at most {MAX_LINEAGE_DEPTH}\n"
        f"{rule}"
    )


def _outcome_rules() -> str:
    """The three outcomes and the one fenced block that reports them."""
    return (
        "Decide EXACTLY ONE of three outcomes.\n\n"
        "`single` -- the committed work is one coherent change despite its "
        "size, and the orchestrator publishes it as it stands. Size alone is "
        "not a reason to split. A diff dominated by legitimate generated or "
        "data artifacts -- a lockfile, a regenerated schema or client, a "
        "golden fixture, a vendored tree, a data or message catalog, a "
        "migration -- is a small change with a large diff, and the fast "
        'answer is `single` with `"category": "generated_artifacts"`.\n\n'
        "`split` -- the committed work covers several separable changes. "
        "Propose the child issues that partition the DECLARED SCOPE "
        "COMPLETELY: every part of that scope belongs to exactly one child, "
        "no child depends on work no child owns, and no child is itself big "
        "enough to need decomposing again. The children reuse this committed "
        "work rather than starting over, so describe each one by the slice "
        "of it that child owns.\n\n"
        "`question` -- neither of the above is safe, and a human has to "
        "decide. If the diff is dominated by generated or data artifacts "
        "that look like they should NOT have been committed at all, this is "
        "the outcome: say what you found rather than deciding it yourself.\n\n"
        "End your final message with EXACTLY ONE fenced JSON block in this "
        "format (and nothing else after it):\n\n"
        "```orchestrator-late-manifest\n"
        "{\n"
        '  "decision": "split",\n'
        '  "rationale": "<<= 2 sentences why>",\n'
        '  "children": [\n'
        '    {"title": "...", "body": "...", "depends_on": []}\n'
        "  ]\n"
        "}\n"
        "```\n\n"
        "The block must be valid JSON parseable by `json.loads`, and "
        "`decision` must be exactly the string `\"single\"`, `\"split\"`, or "
        "`\"question\"` (no other values, no union syntax). Unlike the "
        "initial decomposer, prose alone is not an outcome here: a reply with "
        "no block, or with more than one, is parked for a human rather than "
        "guessed at, so ask through `\"question\"` instead.\n\n"
        '- On `"single"`: omit `"children"`. Give `"rationale"` (<= 2 '
        'sentences); `"category"` is optional and worth setting when the '
        "verdict has a reason worth counting.\n"
        f'- On `"split"`: `"children"` is a non-empty list of at most '
        f"{_MAX_CHILDREN} entries, each with a non-empty `\"title\"` and "
        '`"body"`. `"depends_on"` is a list of 0-based indexes into THIS '
        "children array (not GitHub issue numbers; the orchestrator allocates "
        "those). Self-dependencies and cycles are rejected.\n"
        '- On `"question"`: omit `"children"`, and give `"question"` (the one '
        'specific thing you are asking) and `"category"`.\n\n'
        f"`\"category\"` must be one of {_CATEGORIES}. Anything else is "
        "recorded as `unknown` rather than as what you wrote."
    )
