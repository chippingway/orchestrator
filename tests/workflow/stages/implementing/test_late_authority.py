# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What an adjudication is worth at the gate without a human behind it.

An oversized candidate publishes without a reading only where two records name
it: the exemption a settlement wrote, and the terms an operator authorized
that publication on. These pin down the second half -- what the gate does with
an exemption standing alone, which is the shape an older binary left on live
issues and the shape a damaged authorization leaves on any of them.

What that costs is the measurement, and the reading then decides: a candidate
at or below the ceiling publishes exactly as it always did, and an oversized
one is parked for the authorization rather than routed back into an
adjudication that has already answered. The park's own recovery is here too,
because the command that ends it is the only thing that can.
"""

from __future__ import annotations

import unittest

from orchestrator import config
from orchestrator.git.measurement.models import FingerprintFailure
from orchestrator.workflow.stages.implementing import (
    late_consent as _consent,
    late_parks as _parks,
)
from tests.workflow.fixtures import (
    LABEL_DECOMPOSING,
    MEASURED_BASE_SHA,
    MEASURED_CANDIDATE_SHA,
    SHA_LENGTH,
    _agent,
    _authorize_command,
    _authorized_exemption,
    _damaged_authorization,
    _legacy_exemption,
)
from tests.workflow.interleaving import _RacesTheStep
from tests.workflow.stages.implementing import (
    late_authority_test_support as legacy,
    late_gate_test_support as support,
)

_DECOMPOSING = (support.GATE_ISSUE_NUMBER, LABEL_DECOMPOSING)
_KEY_APPROVED_SHA = "late_approved_sha"
_KEY_APPROVED_BASIS = "late_approved_basis"
_KEY_EXEMPT_SHA = "late_exempt_sha"
_MAX_ADDED_LINES = "MAX_ADDED_LINES"
_OTHER_SHA = "d" * SHA_LENGTH

# How much of a whole object id a hand edit leaves behind, which is the shape
# an exemption field reads back from as no exemption at all.
_ABBREVIATED = 7


def _adjudication_debt() -> dict:
    """The publication debt an authorized settlement's handoff records."""
    return {
        _KEY_APPROVED_SHA: MEASURED_CANDIDATE_SHA,
        _KEY_APPROVED_BASIS: str(_parks.LateApprovalBasis.ADJUDICATION),
    }


def _reading_debt() -> dict:
    """The debt this gate's own count at or below the ceiling records."""
    return {
        _KEY_APPROVED_SHA: MEASURED_CANDIDATE_SHA,
        _KEY_APPROVED_BASIS: str(_parks.LateApprovalBasis.READING),
    }

# What an operator writes to end the park, and the three replies that are not
# it: a paragraph mentioning the command, the command for a commit this issue
# is not holding, and the command with an id nothing here could read.
_AUTHORIZE = _authorize_command()
_AUTHORIZE_IN_PROSE = f"looks fine to me, so: {_AUTHORIZE}"
_AUTHORIZE_ANOTHER = _authorize_command(_OTHER_SHA)
# The command as somebody types it from a `git log` line: recognized, and
# naming no commit this domain could compare anything against.
_AUTHORIZE_ABBREVIATED = _authorize_command(
    MEASURED_CANDIDATE_SHA[:_ABBREVIATED],
)

# The id the fixture's first reply carries. Every reply after it is numbered
# off the thread, because the batches that matter have a word after the first
# and a tick between them has posted a sentence of its own.
_REPLY_ID = support.REPLY_COMMENT_ID

# The half of the notice that differs by the side of publication it is taken
# on: an offer only the seam with a resume behind it may make.
_RESUMED_AGAINST_IT = "the developer is resumed against it"

# What a human posts while the tick that read their authorization is still
# writing. Its whole point is arriving too late to be read and early enough to
# be swallowed by a watermark taken from the thread's tip.
_RETRACTION = "actually, hold off on that"


class UnauthorizedExemptionTest(
    legacy._LegacyExemptionCase, unittest.TestCase,
):
    """An exemption alone lets nothing past: the candidate is measured."""

    def test_an_unauthorized_exemption_is_measured(self) -> None:
        # Both shapes reach the same place. The legacy comment never had an
        # authorization on it, and the damaged one has a group this build
        # cannot read whole -- and a bypass nobody can show the terms of is
        # worth exactly what a bypass nobody granted is worth.
        for shape, seeded in (
            ("legacy", _legacy_exemption()),
            ("damaged", _damaged_authorization()),
        ):
            with self.subTest(shape=shape):
                self.setUp()
                self._seed(**seeded)

                mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

                self._assert_measured(mocks)
                self._assert_held(mocks)

    def test_an_authorized_one_still_publishes(self) -> None:
        # The other side of the same rule, so the refusals above are about the
        # missing half rather than about the exemption having stopped working.
        self._seed(**_authorized_exemption())

        mocks = self._run_gate()

        self._assert_unmeasured(mocks)
        self._assert_published(mocks)

    def test_a_small_candidate_still_publishes(self) -> None:
        # What "measured like any other candidate" means at the other end of
        # the reading: nothing about a legacy exemption holds a change the
        # ceiling would have let through.
        self._seed_legacy()

        mocks = self._run_gate(added_lines=support.SMALL_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_published(mocks)

    def test_the_exact_ceiling_publishes(self) -> None:
        # The boundary is inclusive and stays inclusive here: a candidate
        # exactly at the configured value is not oversized, so it never
        # reaches the park at all.
        self._seed_legacy()

        with support.patch.object(
            config, _MAX_ADDED_LINES, support.SMALL_ADDITIONS,
        ):
            mocks = self._run_gate(added_lines=support.SMALL_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_published(mocks)


class UnauthorizedDebtTest(legacy._LegacyExemptionCase, unittest.TestCase):
    """Whose decision a publication debt rests on, and who may spend it.

    An approval is spent by the tick that comes back after a crash without
    asking anybody, so the only thing that decides whether one may be spent is
    what it RESTS on -- which is why the record says, and why every case here
    is about a basis rather than about the records standing beside it.
    """

    def test_the_exemptions_own_debt_does_not_bypass(self) -> None:
        # The settlement writes the exemption and the approval in one breath,
        # so an approval it recorded is that adjudication wearing another
        # field rather than a reading this gate took. Read as an ordinary
        # approval it would publish the very candidate the record above it may
        # not. An approval an older binary wrote says nothing about its own
        # grounds, and there the exemption is the only evidence left -- so it
        # is read, and read conservatively.
        for described, debt in (
            ("recorded as the adjudication's", _adjudication_debt()),
            ("an older binary's, with no basis", {
                _KEY_APPROVED_SHA: MEASURED_CANDIDATE_SHA,
            }),
        ):
            with self.subTest(debt=described):
                self.setUp()
                self._seed_legacy(**debt)

                mocks = self._run_gate(
                    added_lines=support.OVERSIZED_ADDITIONS,
                )

                self._assert_measured(mocks)
                self._assert_held(mocks)

    def test_a_damaged_exemption_frees_nothing(self) -> None:
        # The crash state the other way round, and the two shapes it comes in.
        # A recorded basis says the debt is the settlement's whatever the
        # exemption beside it reads as. Without one -- an approval an older
        # binary wrote -- the exemption is the only evidence there is, and a
        # field this build cannot read is not the same thing as an issue that
        # never entered an adjudication: it CLAIMS one and cannot say which
        # commit, which is exactly what a hand edit of that one field
        # produces. Read alike, the truncated record is the shape that
        # publishes an adjudication's debt unmeasured.
        for described, debt in (
            ("recorded as the adjudication's", _adjudication_debt()),
            ("an older binary's, with no basis", {
                _KEY_APPROVED_SHA: MEASURED_CANDIDATE_SHA,
            }),
        ):
            with self.subTest(debt=described):
                self.setUp()
                self._seed(**{
                    **debt,
                    _KEY_EXEMPT_SHA: MEASURED_CANDIDATE_SHA[:_ABBREVIATED],
                })

                mocks = self._run_gate(
                    added_lines=support.OVERSIZED_ADDITIONS,
                )

                self._assert_measured(mocks)
                self._assert_held(mocks)

    def test_an_authorized_debt_is_revalidated(self) -> None:
        # The crash window an authorized publication opens. The gate counted
        # this candidate and a human let it past, so the approval it left
        # rests on that gesture -- and a record damaged between the approval
        # and the push has to take the bypass down with it. Recorded as an
        # ordinary reading it would look like a count under the ceiling and
        # publish an oversized change nothing can show the grounds for.
        self._seed_legacy(**{
            _KEY_APPROVED_SHA: MEASURED_CANDIDATE_SHA,
            _KEY_APPROVED_BASIS: str(_parks.LateApprovalBasis.AUTHORIZATION),
        })

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_measured(mocks)
        self._assert_held(mocks)

    def test_an_authorized_publication_records_it(self) -> None:
        # And the basis the road actually writes, so the case above is about
        # this publication rather than about a value nothing produces. Read as
        # the comment stood BEFORE the push, since the landing that pays a
        # debt is also what drops it.
        self._park_awaiting_authorization(_AUTHORIZE)
        recorded = support._RecordAtHandoff(self.github, support.FIND_OPEN_PR)

        with recorded.held():
            self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self.assertEqual(
            recorded.pinned[_KEY_APPROVED_BASIS],
            str(_parks.LateApprovalBasis.AUTHORIZATION),
        )

    def test_a_gate_owned_approval_still_bypasses(self) -> None:
        # And the approval this gate owns is untouched, exemption or no
        # exemption. A candidate the reading found at or below the ceiling on
        # an issue still carrying an older binary's exemption earns a genuine
        # approval, and a crash before the push must not re-judge it against a
        # base that has moved since -- which is the whole of what the approval
        # bypass is for.
        for described, seeded in (
            ("no exemption", {}),
            ("a legacy exemption beside it", _legacy_exemption()),
        ):
            with self.subTest(record=described):
                self.setUp()
                self._seed(**{**seeded, **_reading_debt()})

                mocks = self._run_gate()

                self._assert_unmeasured(mocks)
                self._assert_published(mocks)


class AuthorizationParkTest(legacy._LegacyExemptionCase, unittest.TestCase):
    """What an oversized reading of an adjudicated candidate earns."""

    def test_it_parks_rather_than_re_adjudicating(self) -> None:
        # The change has been ruled one change already. Routing it back would
        # pay for a second adjudicator over an answered question, and a
        # `split` there would cut children out of work somebody decided ships
        # whole -- so the issue stops for the one thing that is missing.
        self._seed_legacy()

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_held(mocks)
        self._assert_waiting_for_authorization()
        self.assertNotIn(_DECOMPOSING, self.github.label_history)

    def test_it_deletes_nothing_and_keeps_the_pair(self) -> None:
        # The record is what an authorization would be checked against, so the
        # park repairs nothing -- and it keeps the pair the freeze wrote,
        # which is what the notice and the announce-once guard are about.
        self._seed_legacy()

        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_kept_the_record()
        self._assert_frozen()

    def test_the_count_is_not_made_durable(self) -> None:
        # A generation carrying a reading past its ceiling is what this
        # workflow means by an adjudication in flight: the dispatcher puts
        # `workflow:decomposing` back over one, and the coordinator pays for a
        # fresh adjudicator. A candidate waiting on an operator is neither, so
        # the count stays out of the record and the reading is re-taken by the
        # tick that acts.
        self._seed_legacy()

        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self.assertIsNone(self._pinned().get(support.KEY_ADDITIONS))

    def test_a_second_poll_leaves_the_label_alone(self) -> None:
        # The whole point of the line above, asked where it actually bites: a
        # poll of a parked issue meets the dispatcher's guards first, and a
        # record reading as a live adjudication would be relabelled out from
        # under the park before any stage saw it.
        self._seed_legacy()
        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._poll(added_lines=support.OVERSIZED_ADDITIONS)

        self.assertNotIn(_DECOMPOSING, self.github.label_history)
        self._assert_waiting_for_authorization()

    def test_the_notice_names_the_command(self) -> None:
        # Before there is a pull request the ordinary resume is still in front
        # of this issue, so the notice offers the other reply too -- and it is
        # true here: guidance falls through the park's own recovery to the
        # road that feeds it to the developer.
        self._seed_legacy()

        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self.assertEqual(len(self.github.posted_comments), 1)
        said = self.github.posted_comments[0][1]
        self.assertIn(config.HITL_MENTIONS, said)
        self.assertIn(_AUTHORIZE, said)
        self.assertIn(str(support.OVERSIZED_ADDITIONS), said)
        self.assertIn(str(config.MAX_ADDED_LINES), said)
        self.assertIn(_RESUMED_AGAINST_IT, said)
class AuthorizationRecoveryTest(
    legacy._LegacyExemptionCase, unittest.TestCase,
):
    """The command that ends the park, and every reply that does not."""

    def test_the_command_records_the_terms(self) -> None:
        # The authorization is written from the gate's own reading rather than
        # from anything the comment already carried: a human authorizes a
        # change of THIS size against THAT ceiling, and only the owner that
        # counted can say either.
        self._park_awaiting_authorization(_AUTHORIZE)

        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        pinned = self._pinned()
        self.assertEqual(
            pinned[support.KEY_OVERRIDE_CANDIDATE_SHA], MEASURED_CANDIDATE_SHA,
        )
        self.assertEqual(
            pinned[support.KEY_OVERRIDE_BASE_SHA], MEASURED_BASE_SHA,
        )
        self.assertEqual(
            pinned[support.KEY_OVERRIDE_ADDITIONS], support.OVERSIZED_ADDITIONS,
        )
        self.assertEqual(
            pinned[support.KEY_OVERRIDE_THRESHOLD], support.GATE_THRESHOLD,
        )
        self.assertEqual(pinned[support.KEY_OVERRIDE_COMMENT_ID], _REPLY_ID)

    def test_the_command_publishes_the_candidate(self) -> None:
        # What the record buys on the same tick: the park comes down, the
        # candidate goes out on the reading it was authorized over, and
        # nothing pays for a developer over work that is already committed.
        # The reading is taken here rather than read back, which is what makes
        # the recorded terms answerable at all.
        self._park_awaiting_authorization(_AUTHORIZE)

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_no_agent(mocks)
        self._assert_measured(mocks)
        self._assert_published(mocks)
        pinned = self._pinned()
        self.assertFalse(pinned[support.AWAITING_HUMAN])
        self.assertIsNone(pinned[support.PARK_REASON])
        self.assertEqual(pinned[support.LAST_ACTION_COMMENT_ID], _REPLY_ID)

    def test_a_lost_reading_leaves_the_park(self) -> None:
        # Nothing about a store that cannot hand back the content between two
        # commits it holds is the operator's doing, so the next tick takes the
        # same reading rather than asking them to authorize twice.
        mocks = self._unreadable_contribution()

        self._assert_held(mocks)
        self._assert_waiting_for_authorization()
        self._assert_kept_the_record()

    def test_the_standing_park_is_not_announced_twice(self) -> None:
        # The same road re-measures the pair the park was taken over and
        # re-takes the park, which is the one way the gate is entered while
        # somebody is still waiting behind it. Said again, the notice would
        # mention the same people about a decision they have already made.
        self._unreadable_contribution()

        self.assertEqual(self.github.posted_comments, [])

    def test_guidance_resumes_the_developer_instead(self) -> None:
        # The two say opposite things -- one that the change publishes as it
        # stands, the other that it has to be different -- and the safe
        # reading of a human who wrote either publishes nothing.
        self._park_awaiting_authorization(_AUTHORIZE_IN_PROSE)

        mocks = self._run_gate(
            run_agent=_agent(
                session_id=support.DEV_SESSION, last_message="revised",
            ),
            added_lines=support.OVERSIZED_ADDITIONS,
        )

        self._assert_resumed(mocks)
        self.assertNotIn(support.KEY_OVERRIDE_CANDIDATE_SHA, self._pinned())

    def test_a_reply_landing_mid_write_survives(self) -> None:
        # The reading picked the last word the thread had when it looked, and
        # a retraction posted while this tick was still writing is not one of
        # the comments it examined. Consumed to the tip of the thread as it
        # stands NOW, that retraction would be swallowed unread and unanswered
        # while the authorization it retracts published -- so the watermark
        # goes only as far as the reading got, and the next poll still has it.
        self._park_awaiting_authorization(_AUTHORIZE)
        landed = []
        racing = _RacesTheStep(
            _consent._recorded_authorization,
            lambda: landed.append(self._reply(_RETRACTION)),
        )

        with support.patch.object(_consent, "_recorded_authorization", racing):
            mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_published(mocks)
        self.assertEqual(len(landed), 1)
        self.assertLess(
            self._pinned()[support.LAST_ACTION_COMMENT_ID], landed[0],
        )

    def _unreadable_contribution(self):
        """The authorized park re-entered on a host that cannot fingerprint."""
        self._park_awaiting_authorization(_AUTHORIZE)
        return self._run_gate(
            contribution_digest=FingerprintFailure.CONTENT_ABSENT,
            added_lines=support.OVERSIZED_ADDITIONS,
        )


class RefusedCommandTest(legacy._LegacyExemptionCase, unittest.TestCase):
    """Every command this park owes an answer to and may not act on.

    One gesture, three ways of not being actionable: it names another commit,
    it names no commit at all, or the right one arrives behind either. All
    three are ANSWERED and consumed rather than dropped -- the seams that
    publish onto a pull request the remote already carries move the watermark
    by no other means, so a reply left standing would be in every later batch
    and would refuse the correct command behind it for as long as the park
    stood.
    """

    def test_another_commits_command_is_answered(self) -> None:
        # A bypass may license exactly what a human looked at, and an id
        # copied out of a notice about work the developer has since been
        # resumed over is not this candidate. It is ANSWERED and consumed
        # rather than ignored: left in the batch it would stand in every later
        # reading and refuse the correct command behind it.
        self._park_awaiting_authorization(_AUTHORIZE_ANOTHER)

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self.assertNotIn(support.KEY_OVERRIDE_CANDIDATE_SHA, self._pinned())
        self._assert_held(mocks)
        self._assert_waiting_for_authorization()
        self.assertIn(
            MEASURED_CANDIDATE_SHA, self.github.posted_comments[-1][1],
        )
        self._assert_consumed_its_own_answer()

    def test_an_abbreviated_command_is_answered(self) -> None:
        # A command nobody could act on is still a gesture this park owes an
        # answer to. Dropped as though it were guidance, an operator who
        # abbreviated would be left with a silent park, a thread that never
        # said why, and a reply standing in every later batch.
        self._park_awaiting_authorization(_AUTHORIZE_ABBREVIATED)

        mocks = self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_held(mocks)
        self._assert_waiting_for_authorization()
        self.assertIn(
            MEASURED_CANDIDATE_SHA, self.github.posted_comments[-1][1],
        )
        self._assert_consumed_its_own_answer()

    def test_a_refusal_is_not_read_as_guidance(self) -> None:
        # Comment ids ascend across a thread, so the sentence a refusal posts
        # lands ABOVE the reply it answers. Consumed only as far as that
        # reply, the orchestrator's own words are what the next poll finds
        # past the watermark -- and the resume reads whatever is there as a
        # human's, spawning a developer against a refusal nobody wrote.
        self._park_awaiting_authorization(_AUTHORIZE_ANOTHER)
        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)

        mocks = self._poll(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_no_agent(mocks)
        self.assertEqual(len(self.github.posted_comments), 1)

    def test_a_refused_command_poisons_nothing(self) -> None:
        # The command a human gets right after getting one wrong has to work,
        # and on the seams that publish onto a pull request the remote already
        # carries nothing else ever moves the watermark. Read as a set instead
        # of as a last word, the first reply would refuse every one behind it.
        self._park_awaiting_authorization(_AUTHORIZE_ANOTHER)
        self._run_gate(added_lines=support.OVERSIZED_ADDITIONS)
        corrected = self._reply(_AUTHORIZE)

        mocks = self._poll(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_published(mocks)
        self.assertEqual(
            self._pinned()[support.KEY_OVERRIDE_COMMENT_ID], corrected,
        )

    def test_guidance_before_it_poisons_nothing(self) -> None:
        # The same batch the other way round, and the ordering is the answer:
        # a human who asked for a change and then asked for it to publish has
        # decided about the second. Read as a set, the guidance would refuse
        # the command standing behind it for as long as the park stood.
        self._park_awaiting_authorization("make it smaller, please")
        decided = self._reply(_AUTHORIZE)

        mocks = self._poll(added_lines=support.OVERSIZED_ADDITIONS)

        self._assert_no_agent(mocks)
        self._assert_published(mocks)
        self.assertEqual(
            self._pinned()[support.KEY_OVERRIDE_COMMENT_ID], decided,
        )

    def _assert_consumed_its_own_answer(self) -> None:
        """The watermark is past the sentence, not merely past the reply.

        Ids ascend across a thread, so a refusal lands above the command it
        answers. Left between the two, the orchestrator's own words are what
        the next poll reads as a human's fresh reply.
        """
        watermark = self._pinned()[support.LAST_ACTION_COMMENT_ID]

        self.assertGreater(watermark, _REPLY_ID)
        self.assertEqual(
            watermark, self.github.latest_comment_id(self.issue),
        )


if __name__ == "__main__":
    unittest.main()
