# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The carriers one late adjudication hands between its owners.

The late mode is additive: an oversized committed candidate is adjudicated
under the same `workflow:decomposing` label the initial decomposer runs under,
by a separate set of owners that share these records. They sit together
because each of them crosses a boundary the call stack alone would lose it
across -- the tick's own subject, which advances as the generation is
persisted; what reconciling the plan-PR hold left behind; the run this issue is
locked to as the pinned comment records it; what one late reply decided; and
what the whole call did with the tick it was given.

`_LateRun` is the durable half. It records what the failure contract calls the
late agent's own facts -- the role it ran as, the backend spec it is locked
to, the session it opened, the cycle, generation, and exact source commit it
was spawned against, and the result it completed with -- so a tick that
crashed after a finished run reads the answer back rather than paying for a
second one, which would not be free and would be free to decide differently.
The result it records is the WHOLE of what the verdict decided, the child
manifest of a split included; the one part deliberately left out is the
agent's rationale, which is prose nothing acts on. An outcome the pinned
comment cannot hold is refused entire rather than shortened, because half an
answer read back later is worse than none.

`_LateDisposition` is not a durable vocabulary and is spelled as a plain
`Enum` for that reason: nothing writes it to the pinned comment or to a sink,
so a member renamed here is a refactor rather than the migration a `StrEnum`
member in this domain would be.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from github.Issue import Issue

from orchestrator import config
from orchestrator.github.client import GitHubClient
from orchestrator.github.pinned_state import PinnedState
from orchestrator.workflow.late_split.events import LateVerdictCategory
from orchestrator.workflow.late_split.models import LateGeneration, LateVerdict

# The role a late adjudication is recorded under. It is the decomposer's --
# the question being answered is a decomposition question -- and it is stored
# beside the run rather than assumed, because the same coordinator owns the
# developer revision a trusted answer earns, which records its own role.
_DECOMPOSER_ROLE = "decomposer"


class _LateDisposition(Enum):
    """What one late-adjudication call did with the tick it was given."""

    NOT_LATE = "not_late"
    PARKED = "parked"
    DEFERRED = "deferred"
    DECIDED = "decided"


@dataclass(frozen=True)
class _LateAdjudication:
    """What one late reply decided, once its fenced block was believed.

    A verdict is always present -- a reply that could not produce one is a
    parse error and never becomes one of these -- and the rest is what that
    verdict is allowed to carry. `children` is the manifest a `split`
    proposes, held in memory for the tick that acts on it.
    """

    verdict: LateVerdict
    category: Optional[LateVerdictCategory] = None
    rationale: str = ""
    question: str = ""
    children: tuple[dict, ...] = ()

    @property
    def child_count(self) -> Optional[int]:
        """How many children a split proposed, and nothing for the others.

        The verdict event's contract, answered where the manifest is: a child
        count belongs to a `split` and to no other verdict, in both
        directions.
        """
        if self.verdict != LateVerdict.SPLIT:
            return None
        return len(self.children)


@dataclass(frozen=True)
class _LateRun:
    """The late run one issue is locked to, as pinned state records it.

    The spec is the whole configured command rather than the backend alone,
    for the reason every other role's pin is: a resume has to land on the CLI
    that issued the session id, and configured args are part of what a later
    run must reproduce.

    The result is the whole of what the verdict decided, not a marker for it.
    A `single` needs nothing beside itself; a `question` carries the category
    it was asked under and the sentence it asked, because announcing it is the
    outcome's own external effect and a crash between recording and posting
    has to be able to finish it; a `split` carries the child manifest, because
    that manifest IS what the split decided and a record without it would
    refuse the re-run while the answer it stands for was gone.
    """

    role: str = _DECOMPOSER_ROLE
    spec: str = ""
    backend: str = ""
    extra_args: tuple[str, ...] = ()
    session_id: Optional[str] = None
    cycle_id: int = 0
    source_sha: str = ""
    generation: int = 0
    verdict: Optional[LateVerdict] = None
    category: Optional[LateVerdictCategory] = None
    question: str = ""
    children: tuple[dict, ...] = ()

    @property
    def is_actionable(self) -> bool:
        """Whether the recorded outcome is one a caller could act on.

        Asked per verdict, because what "complete" means differs by verdict
        and a half-written one is worse than none: a `question` with no
        sentence and no category suppresses the next spawn and then announces
        nothing, and a `split` with no children suppresses it and then names
        no children to create. Either would leave the issue decided, silent,
        and going nowhere -- so an incomplete record is not an answer, and the
        adjudicator runs again.
        """
        if self.verdict == LateVerdict.SINGLE:
            return True
        if self.verdict == LateVerdict.QUESTION:
            return bool(self.question) and self.category is not None
        if self.verdict == LateVerdict.SPLIT:
            return bool(self.children)
        return False

    def answers(self, generation: LateGeneration) -> bool:
        """Whether a recorded result already decides THIS candidate.

        All three parts of the identity are required, because any of them
        alone would let a stale answer through. The generation counter is not
        unique on its own: a restart mints a fresh CYCLE and puts the counter
        back to where it started, so generation 1 of cycle 4 is a different
        attempt from generation 1 of cycle 3 -- and these run fields survive a
        late-generation clear, which is exactly the window a repeated counter
        would be read in. The commit is required beside them because a
        candidate replaced within one generation is a different question.

        A record that is not actionable is unanswered whatever identity it
        carries: re-adjudicating costs one more agent run, while acting on a
        verdict whose substance nothing kept would cost whatever that verdict
        was about.
        """
        if not self.is_actionable or not self.source_sha:
            return False
        return (
            self.cycle_id == generation.cycle_id
            and self.generation == generation.generation
            and self.source_sha == generation.candidate_sha
        )



@dataclass(frozen=True)
class _PlanPr:
    """One plan pull request, read once and under one guard.

    A PyGithub pull request is lazy: the object a fetch returns has asked
    GitHub nothing, and the request that can fail is the FIRST attribute read.
    A caller that guarded only the fetch would therefore guard almost nothing
    -- the failure lands later, on the head, the state, or the body, in the
    middle of deciding whether to replace a human's description.

    So every field a decision is made on is read where the fetch is guarded
    and carried here as a plain value. What is left of the pull request is the
    handle the edit is made against, and that write has a guard of its own.
    """

    pull_request: object
    number: int
    body: str
    head_sha: str
    pr_state: str


@dataclass(frozen=True)
class _PlanPrHold:
    """What reconciling the generation-marked plan-PR hold left behind.

    `held` and `failed` are not opposites. A generation with no reusable open
    plan PR is neither -- there is nothing to hold and nothing went wrong --
    and the caller spawns exactly as it would have. Only `failed` stops a
    spawn.
    """

    generation: LateGeneration
    held: bool = False
    failed: bool = False


@dataclass
class _LateContext:
    """The one tick a late adjudication runs inside.

    Mutable in two fields. `generation` is replaced as each step persists what
    it reached, so every owner after that step reads the record the pinned
    comment now holds rather than the one the tick opened on. `retired_park`
    is what this tick cleared, kept because clearing a park is not the same as
    the human it named never having been told: a park retired here and re-taken
    for the same reason is the same park, and repeating its notice would say
    the same thing to the same thread again.
    """

    gh: GitHubClient
    spec: config.RepoSpec
    issue: Issue
    state: PinnedState
    generation: LateGeneration
    retired_park: Optional[str] = None


@dataclass(frozen=True)
class _LateAdjudicationRun:
    """What one call to the late coordinator did, and what it decided.

    `run` is the record pinned state holds once this call is over, read back
    rather than assembled, so a caller reading a session id off it is reading
    the one a later resume would land on rather than the one the tick opened
    with.

    `adjudication` is present on every `DECIDED` answer, whether this tick's
    own agent produced it or a crashed one already had: a recovered outcome is
    rebuilt from the record, which carries the whole of what each verdict
    decided. Only the agent's own rationale is missing from a rebuilt one --
    prose the pinned comment deliberately does not keep.
    """

    disposition: _LateDisposition
    generation: LateGeneration
    run: _LateRun
    adjudication: Optional[_LateAdjudication] = None
