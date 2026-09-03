# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The charge a launch takes at the boundary a process is invoked from.

Five promises are pinned here, each one something the lifetime ceiling above
this owner is worth nothing without: a charge that is durable before the
process exists, a crash window a later launch can recognize, a refusal that
invokes nothing at all, a caller whose own staged fields are not published by
somebody else's write, and a run whose ending -- exception, interruption, or
an ordinary exit -- never hands the charge back.
"""
from __future__ import annotations

import unittest

from tests.workflow.engine import run_circuit_test_support as support


class ChargedLaunchTest(unittest.TestCase):
    """What an ordinary launch pays, and when it has paid it."""

    def test_the_charge_is_durable_before_the_process(self) -> None:
        # Charged behind the spawn instead, a run that crashed, timed out, or
        # was killed mid-flight would be one the ledger never saw.
        launch = support.run_launch(support.seeded())

        self.assertEqual(launch.invocations, 1)
        observed = launch.observed[0]
        self.assertEqual(observed[support.USED], 1)
        self.assertEqual(observed[support.RESERVATION], support.STARTED)
        self.assertEqual(observed[support.FINGERPRINT], support.fingerprint())

    def test_the_two_phases_are_written_apart(self) -> None:
        # The window between them is the only thing a later tick can tell a
        # launch that never ran from one that did by.
        launch = support.run_launch(support.seeded())

        self.assertEqual(
            launch.phases, [support.RESERVED, support.STARTED],
        )

    def test_the_caller_is_handed_the_charge(self) -> None:
        # Without it the handler's own write at the end of the run would put
        # the count back the way its read found it, and the issue would have
        # paid for a run its ledger no longer records.
        launch = support.run_launch(support.seeded())

        self.assertEqual(launch.state.get(support.USED), 1)
        self.assertEqual(
            launch.state.get(support.RESERVATION), support.STARTED,
        )

    def test_an_unlimited_ceiling_still_charges(self) -> None:
        # The setting decides what to do about the total, not whether runs
        # happened: a meter that paused under it would report an issue that
        # ran all day as having spent nothing once it came back on.
        launch = support.run_launch(
            support.seeded(**{support.USED: 99}), allowance=0,
        )

        self.assertEqual(launch.invocations, 1)
        self.assertEqual(launch.spent, 100)
        self.assertFalse(launch.durable.get(support.AWAITING_HUMAN))


class CrashWindowTest(unittest.TestCase):
    """Which standing charge a launch may run on, and which it may not."""

    def test_a_charge_this_launch_took_is_reused(self) -> None:
        # A tick that died between the two writes left a run charged and
        # never spawned; paying again would spend a lifetime on crashes.
        launch = support.run_launch(support.seeded(**{
            support.USED: 1,
            support.RESERVATION: support.RESERVED,
            support.FINGERPRINT: support.fingerprint(),
        }))

        self.assertEqual(launch.invocations, 1)
        self.assertEqual(launch.spent, 1)
        self.assertEqual(launch.phases, [support.STARTED])

    def test_a_start_marker_charges_a_new_attempt(self) -> None:
        # Past that marker a process may have run and nothing on the issue can
        # say it did not, so the next launch pays for itself.
        launch = support.run_launch(support.seeded(**{
            support.USED: 1,
            support.RESERVATION: support.STARTED,
            support.FINGERPRINT: support.fingerprint(),
        }))

        self.assertEqual(launch.spent, 2)
        self.assertEqual(
            launch.phases, [support.RESERVED, support.STARTED],
        )

    def test_another_launchs_charge_is_not_claimed(self) -> None:
        # A charge some other road recorded is one this launch never paid
        # for, and the ledger would stop recording what each run cost.
        launch = support.run_launch(support.seeded(**{
            support.USED: 1,
            support.RESERVATION: support.RESERVED,
            support.FINGERPRINT: support.OTHER_LAUNCH,
        }))

        self.assertEqual(launch.spent, 2)
        self.assertEqual(
            launch.durable[support.FINGERPRINT], support.fingerprint(),
        )

    def test_a_resumed_session_is_its_own_launch(self) -> None:
        # The fingerprint is what a request IS, so a resume of a session the
        # charge was never taken under does not inherit it.
        launch = support.run_launch(
            support.seeded(**{
                support.USED: 1,
                support.RESERVATION: support.RESERVED,
                support.FINGERPRINT: support.fingerprint(),
            }),
            resume_session_id="sess-earlier",
        )

        self.assertEqual(launch.spent, 2)


class RefusedLaunchTest(unittest.TestCase):
    """The three refusals, and the one process none of them invokes."""

    def test_a_spent_allowance_invokes_nothing(self) -> None:
        launch = support.run_launch(
            support.seeded(**{support.USED: 1}), allowance=1,
        )

        self.assertEqual(launch.invocations, 0)
        self.assertEqual(launch.spent, 1)
        self.assertEqual(launch.events(support.EVENT_AGENT_SPAWN), [])
        self.assertEqual(launch.events(support.EVENT_AGENT_EXIT), [])

    def test_a_refusal_reads_as_a_run_that_never_ran(self) -> None:
        # Interrupted, so every spawning handler returns without writing
        # durable state for it -- and never invoked, which is what the roads
        # that read the worktree ahead of that guard have to be able to tell:
        # a killed run may have written, and this one cannot have.
        launch = support.run_launch(
            support.seeded(**{support.USED: 1}), allowance=1,
        )

        self.assertFalse(launch.answer.invoked)
        self.assertTrue(launch.answer.interrupted)
        self.assertIsNone(launch.answer.session_id)
        self.assertEqual(
            launch.answer.exit_code, support.NO_PROCESS_EXIT_CODE,
        )
        self.assertFalse(launch.answer.timed_out)

    def test_a_spent_allowance_parks_and_says_so(self) -> None:
        # The park is durable before a word of it is said, and the caller
        # keeps it too -- a handler that writes anyway must not undo it.
        launch = support.run_launch(
            support.seeded(**{support.USED: 1}), allowance=1,
        )

        self.assertTrue(launch.durable[support.AWAITING_HUMAN])
        self.assertEqual(
            launch.durable[support.PARK_REASON],
            support.PARK_AGENT_RUN_LIMIT,
        )
        self.assertTrue(launch.state.get(support.AWAITING_HUMAN))
        self.assertTrue(launch.events(support.RUN_LIMIT_EVENT))

    def test_a_refused_charge_invokes_nothing(self) -> None:
        # A spawn the ledger would never see is exactly the run the ceiling
        # above exists to stop an issue repeating.
        launch = support.seeded()
        launch.gh.refuse_write()

        support.run_launch(launch)

        self.assertEqual(launch.invocations, 0)
        self.assertEqual(launch.durable, {})
        self.assertIsNone(launch.state.get(support.USED))

    def test_a_refused_start_keeps_the_charge(self) -> None:
        # The charge landed, so the caller carries it and the next launch of
        # the same request runs on it rather than paying twice.
        launch = support.seeded()
        launch.gh.refuse_write(after=1)

        support.run_launch(launch)

        self.assertEqual(launch.invocations, 0)
        self.assertEqual(launch.durable[support.RESERVATION], support.RESERVED)
        self.assertEqual(launch.state.get(support.USED), 1)

    def test_an_unusable_pinned_read_invokes_nothing(self) -> None:
        # A request that failed leaves no count to charge against, and a
        # comment that will not parse reads back as an issue that has spent
        # nothing -- charging on it would hand out a whole fresh lifetime.
        for refusal in ("unreadable", "unparsed"):
            with self.subTest(refusal=refusal):
                launch = support.seeded()
                setattr(launch.gh, refusal, True)

                support.run_launch(launch)

                self.assertEqual(launch.invocations, 0)
                self.assertEqual(launch.gh.writes, [])
                self.assertTrue(launch.answer.interrupted)


class CallerStateTest(unittest.TestCase):
    """What the charge carries onto the caller's object, and what it leaves."""

    def test_a_staged_field_is_not_published(self) -> None:
        # A reviewer spec, a moved watermark, a session about to be replaced:
        # those belong to the handler's own write at the END of the run, which
        # is where it decides whether they are kept at all.
        launch = support.seeded()
        launch.state.set("review_agent", "codex:gpt-5")

        support.run_launch(launch)

        self.assertNotIn("review_agent", launch.durable)
        self.assertEqual(launch.state.get("review_agent"), "codex:gpt-5")
        self.assertEqual(launch.state.get(support.USED), 1)

    def test_only_the_charge_comes_back(self) -> None:
        # A durable field the caller never read is not this write's to hand
        # over: the caller's copy may hold a staged edit of the same field,
        # and the charge is not the write that decides it.
        launch = support.seeded(decomposer_agent="codex")
        launch.state.data.pop("decomposer_agent")

        support.run_launch(launch)

        self.assertNotIn("decomposer_agent", launch.state.data)
        self.assertEqual(launch.state.get(support.USED), 1)


class FinishedRunTest(unittest.TestCase):
    """Every ending a launched process can have keeps the run it spent."""

    def test_a_runner_exception_keeps_the_charge(self) -> None:
        # It propagates for the per-issue tick catch above to log, and the
        # charge is already durable because it was taken before the spawn.
        launch = support.seeded()

        with self.assertRaises(RuntimeError):
            support.run_launch(launch, outcome=RuntimeError("codex blew up"))

        self.assertEqual(launch.spent, 1)
        self.assertEqual(launch.durable[support.RESERVATION], support.STARTED)

    def test_a_killed_run_still_counts_as_invoked(self) -> None:
        # The shutdown sweep kills a process that existed and may have written
        # before it died, so what it left is read the way it always was.
        launch = support.run_launch(
            support.seeded(),
            outcome=support.agent_result(
                exit_code=support.INTERRUPTED_EXIT_CODE, interrupted=True,
            ),
        )

        self.assertTrue(launch.answer.invoked)

    def test_an_interrupted_run_keeps_the_charge(self) -> None:
        # The handler returns without writing pinned state, so the charge has
        # to be durable already or a shutdown kill would be a free run.
        launch = support.run_launch(
            support.seeded(),
            outcome=support.agent_result(
                exit_code=support.INTERRUPTED_EXIT_CODE,
                session_id=None,
                interrupted=True,
            ),
        )

        self.assertTrue(launch.answer.interrupted)
        self.assertEqual(launch.spent, 1)
        self.assertEqual(launch.durable[support.RESERVATION], support.STARTED)
