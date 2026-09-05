# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""One oversized candidate walked from the size gate to a settled `single`.

The adjudicated fixture beside this one WRITES the verdict a rebase then
carries; this one earns it. It puts a change past the ceiling on the branch,
sends it through the real size gate, and settles the real adjudicator's
answer -- so what the base advance after it replays is a verdict this workflow
actually reached, over a pair it actually froze, on an issue the route
actually walked.

Three things are stood in for and none of them decides anything: the agent's
reply, the authenticated push, and the remote-side base freeze these fixtures
have no token to take. The push double moves the pull request as well, because
the repository is real and the pull request is a double -- left disagreeing,
every round past the first would be entered on a head the remote no longer
has.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from orchestrator import config
from orchestrator.agents import runner as _agent_runner
from orchestrator.git import branch_transport as _branch_transport
from orchestrator.git.measurement import additions as _additions
from orchestrator.workflow.stages.decomposition import (
    late_coordinator as _coordinator,
    late_reply as _late_reply,
)
from orchestrator.workflow.stages.implementing import (
    late_push as _late_push,
    late_records as _late_records,
)
from orchestrator.workflow.state import WorkflowLabel
from tests.git.base_sync.exemption_git_support import (
    ISSUE,
    AdjudicatedRebaseRealGitFixture,
)
from tests.git.base_sync.real_git_test_support import (
    ADD_COMMAND,
    ORIGIN_REMOTE,
    PR_BRANCH,
    PR_NUMBER,
    PUSH_COMMAND,
    WORKTREES_DIR_NAME,
    _LocalBranchPusher,
)
from tests.git.base_sync.refresh_test_support import _patched
from tests.support.fakes import FakePRRef
from tests.workflow.fixtures import LABEL_VALIDATING, _agent

# The ceiling the journey's candidate is oversized against, and the file that
# puts it there. Both are small enough to keep the real diff cheap and large
# enough that the real counter really crosses the ceiling on the real objects.
JOURNEY_CEILING = 20
JOURNEY_FILE = "oversized.py"
JOURNEY_LINES = 200

# The verdict the adjudicator reaches on that candidate, in the fence the
# reply owner really parses -- taken from that owner rather than retyped, so
# a manifest this build could not read would fail here rather than pass.
SINGLE_MANIFEST = (
    f"```{_late_reply._LATE_BLOCK}\n"
    + '{"decision": "single", "rationale": "one coherent change",'
    + ' "category": "generated_artifacts"}\n```'
)

# The line counter as it is before the shared base-sync doubles replace it. A
# journey about an OVERSIZED candidate has to cross the ceiling on the objects
# themselves, so the real reading is put back for the fixture below.
_REAL_ADDITION_COUNT = _additions._count_added_lines


class _PublishesToThePullRequest(_LocalBranchPusher):
    """A push that moves the pull request this fixture's client answers with.

    The repository is real and the pull request is a double, so a push that
    landed would otherwise leave the two disagreeing about where the branch
    is -- and every gate past it is entered on a head the remote no longer
    has. What a real remote does to `pr.head` is done here, so a journey of
    several rounds reads one branch rather than two.
    """

    def __init__(self, github) -> None:
        super().__init__()
        self._github = github

    def __call__(self, spec, worktree, branch, **options) -> bool:
        """Push, and stand the pull request on whatever the push published."""
        landed = super().__call__(spec, worktree, branch, **options)
        pull_request = self._github.pulls[PR_NUMBER]
        if landed and self.revision:
            pull_request.head = FakePRRef(sha=self.revision)
        return landed


class OversizedJourneyRealGitFixture(AdjudicatedRebaseRealGitFixture):
    """One oversized candidate, adjudicated for real and then rebased for real.

    Every step here is the production one over a real repository: the size
    gate counts the real diff and routes the real generation, the adjudicator
    settles a real `single` and records the exemption and the identity from
    the pair it froze, and the refresh rebases and force-publishes through the
    same gate. What is stood in for is what a fixture cannot have -- the
    agent's reply, the authenticated push, and the remote-side base freeze.
    """

    def setUp(self) -> None:
        super().setUp()
        _patched(self, _additions, "_count_added_lines", _REAL_ADDITION_COUNT)
        _patched(self, config, "MAX_ADDED_LINES", JOURNEY_CEILING)
        # The adjudicator fingerprints the accepted pair in the checkout the
        # configured root names, and this journey's is the real one.
        _patched(
            self, config, "WORKTREES_DIR", self._tmpdir / WORKTREES_DIR_NAME,
        )

    def _commits_an_oversized_candidate(self) -> str:
        """Put a change past the ceiling on the branch and open its review."""
        (self._wt / JOURNEY_FILE).write_text(
            "".join(f"value_{line} = {line}\n" for line in range(JOURNEY_LINES)),
        )
        self._git(ADD_COMMAND, ".", cwd=self._wt)
        self._git(
            "commit", "-m", "feat: add the oversized change",
            cwd=self._wt, env_extra=self._author_env,
        )
        self._git(PUSH_COMMAND, ORIGIN_REMOTE, PR_BRANCH, cwd=self._wt)
        self._open_pull_request(label=LABEL_VALIDATING)
        return self._wt_head()

    def _publishes_as_review(self, candidate: str):
        """Take the publication one `workflow:validating` round makes.

        The same call the reviewer's own route makes, so what decides the
        candidate is the gate rather than anything this fixture arranges: the
        first round is held and routed to the adjudication, and the round
        after the rebase publishes a change the exemption already covers.
        """
        issue = self._gh._issues[ISSUE]
        with patch.object(
            _branch_transport, "_push_branch",
            _PublishesToThePullRequest(self._gh),
        ):
            return _late_push._publishes(
                _late_records._gate(
                    self._gh, self._spec, issue,
                    self._gh.read_pinned_state(issue), self._wt,
                ),
                PR_BRANCH,
                _late_records._Entered(
                    stage=WorkflowLabel.VALIDATING,
                    head=candidate,
                    candidate=candidate,
                ),
            )

    def _accepted_as_single(self):
        """Run the real adjudicator over the frozen pair and settle its verdict.

        The settlement publishes the accepted commit itself -- it is the last
        tick holding the head the verdict was measured over -- so the push it
        makes is a real one against the fixture's own remote.
        """
        issue = self._gh._issues[ISSUE]
        spawn = MagicMock(return_value=_agent(last_message=SINGLE_MANIFEST))
        with patch.object(_agent_runner, "run_agent", spawn), patch.object(
            _branch_transport, "_push_branch",
            _PublishesToThePullRequest(self._gh),
        ):
            return _coordinator._adjudicate_late_generation(
                self._gh, self._spec, issue,
                self._gh.read_pinned_state(issue),
            )

    def _refreshes(self) -> _LocalBranchPusher:
        """Run one refresh over the advanced base and report the push it made."""
        pusher = _PublishesToThePullRequest(self._gh)
        with patch.object(_branch_transport, "_push_branch", pusher):
            self._refresh()
        return pusher

    def _durable(self):
        """The pinned comment as a process starting now would read it."""
        return self._gh.read_pinned_state(self._gh._issues[ISSUE])
