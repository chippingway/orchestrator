# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, layering, and facade checks for base sync."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from orchestrator import base_sync, git
from orchestrator.git.base_sync import (
    conflicts,
    eligibility,
    guards,
    models,
    pr,
    publication,
    state,
)
from orchestrator.git.base_sync import (
    outcomes,
    persistence,
    pre_pr,
    recovery,
    refresh,
    snapshot,
    startup,
)

_MODELS_OWNER = "orchestrator.git.base_sync.models"

_PRE_PR_OWNER = "orchestrator.git.base_sync.pre_pr"

_REFRESH_OWNER = "orchestrator.git.base_sync.refresh"

_STATE_OWNER = "orchestrator.git.base_sync.state"

_PERSISTENCE_OWNER = "orchestrator.git.base_sync.persistence"

_OUTCOMES_OWNER = "orchestrator.git.base_sync.outcomes"

_SNAPSHOT_OWNER = "orchestrator.git.base_sync.snapshot"

_RECOVERY_OWNER = "orchestrator.git.base_sync.recovery"

_STARTUP_OWNER = "orchestrator.git.base_sync.startup"

_ELIGIBILITY_OWNER = "orchestrator.git.base_sync.eligibility"

_PUBLICATION_OWNER = "orchestrator.git.base_sync.publication"

_GUARDS_OWNER = "orchestrator.git.base_sync.guards"

_PR_OWNER = "orchestrator.git.base_sync.pr"

_CONFLICTS_OWNER = "orchestrator.git.base_sync.conflicts"

_OWNERS = (
    _MODELS_OWNER, _PRE_PR_OWNER, _REFRESH_OWNER, _STATE_OWNER,
    _PERSISTENCE_OWNER, _OUTCOMES_OWNER, _SNAPSHOT_OWNER, _RECOVERY_OWNER,
    _STARTUP_OWNER, _ELIGIBILITY_OWNER, _PUBLICATION_OWNER, _GUARDS_OWNER,
    _PR_OWNER, _CONFLICTS_OWNER,
)

_MODULES = ("orchestrator.git.base_sync", *_OWNERS, "orchestrator.base_sync")

# The lazy inventory and its resolver hooks are all `orchestrator/` still
# carries for base sync; both are pure compatibility wiring with no behavior.
_COMPATIBILITY_LEAVES = frozenset((
    "_base_sync_export_manifest.py",
    "_base_sync_exports.py",
))

# The state owner exists to spell out the pinned-state keys and the label
# vocabulary one rebase attempt is routed by, so the label enum and the
# transition graph behind it are the only orchestrator modules it may reach.
# The pre-PR owner adds only the git envelope its rebases run under and the
# repository spec they read their base ref off.
_ALLOWED_MODULES = (
    "orchestrator",
    "orchestrator._package_exports",
    "orchestrator._state_transitions",
    "orchestrator._workflow_labels",
    "orchestrator.state_machine",
)

_ALLOWED_ROOTS = (
    (_STATE_OWNER, ("orchestrator.git",)),
    (_PRE_PR_OWNER, ("orchestrator.config", "orchestrator.git")),
)

# Every owner outside that layer annotates its fields and arguments with the
# composed GitHub client, which drags the analytics and usage graph in behind
# it, so an allowlist would not describe them. What every owner owes is the
# direction of the dependency: none may reach the base-sync leaves, the facade
# over them, the workflow engine and its stage handlers, or an application
# entrypoint. The facade is the sharpest of those, because it resolves the very
# names these owners define -- an owner that imported it would be reading its
# own definitions back out. The collaborators that do live above this package
# -- the park guard and the comment poster in the workflow engine -- are
# reached through call-time imports, which is what keeps them out of this
# check.
_FORBIDDEN_PREFIXES = (
    "orchestrator._base_sync",
    "orchestrator.base_sync",
    "orchestrator.cli",
    "orchestrator.main",
    "orchestrator.stages",
    "orchestrator.verify",
    "orchestrator.workflow",
    "orchestrator.worktree",
)

_LAYERING_SCRIPT = """
import sys
import {module}
print(*sorted(name for name in sys.modules if name.startswith('orchestrator')))
"""

# The initializer binds nothing, so each name stays reachable only through its
# owner or the historical `base_sync` facade.
_OWNER_ONLY_NAMES = (
    "_AUTO_REBASE_PARK_REASONS",
    "_AutoRebaseContext",
    "_AutoRebaseRequest",
    "_PENDING_PUSH_SHA",
    "_auto_rebase_retry_decision",
    "_fetch_recovery_snapshot",
    "_park_dirty_recovery",
    "_publish_auto_rebase",
    "_recover_pending_auto_base_rebase",
    "_refresh_base_and_worktrees",
    "_reset_clear_and_park",
    "_route_pr_worktree_to_resolving_conflict",
    "_start_auto_rebase",
    "_sync_pr_worktree_to_base",
    "log",
)

_FACADE_FORWARDS = (
    ("_AUTO_REBASE_PARK_REASONS", state),
    ("_AWAITING_HUMAN", state),
    ("_AutoRebaseContext", models),
    ("_AutoRebaseDecision", models),
    ("_AutoRebaseRecoveryContext", models),
    ("_AutoRebaseRecoverySnapshot", models),
    ("_AutoRebaseRequest", models),
    ("_CONFLICT_ROUND", state),
    ("_ConflictRouteContext", models),
    ("_ERROR_SNIPPET_LEN", state),
    ("_PARK_REASON", state),
    ("_PENDING_PUSH_SHA", state),
    ("_PR_REFRESH_DETOUR_LABELS", state),
    ("_REASON_AUTO_BASE_REBASE_FAILED", state),
    ("_REASON_AUTO_BASE_REBASE_PUSH_FAILED", state),
    ("_REVIEW_ROUND", state),
    ("_abort_recovery_unverified", snapshot),
    ("_already_published_recovery_notice", outcomes),
    ("_auto_rebase_label_is_eligible", eligibility),
    ("_auto_rebase_recovery_decision", eligibility),
    ("_auto_rebase_retry_decision", eligibility),
    ("_base_sync_issue", refresh),
    ("_clear_ineligible_recovery", snapshot),
    ("_clear_unchanged_recovery", snapshot),
    ("_complete_recovery_snapshot", snapshot),
    ("_emit_auto_rebase_event", publication),
    ("_emit_recovered_rebase_event", persistence),
    ("_fetch_recovery_snapshot", snapshot),
    ("_finalize_already_published_recovery", outcomes),
    ("_finalize_auto_rebase", publication),
    ("_finalize_recovered_rebase", persistence),
    ("_finish_noop_auto_rebase", guards),
    ("_handle_failed_auto_rebase", startup),
    ("_issue_skips_base_sync", refresh),
    ("_issue_worktree_number", refresh),
    ("_merge_base_into_worktree", pre_pr),
    ("_normal_auto_rebase_can_start", eligibility),
    ("_open_auto_rebase_pr", eligibility),
    ("_park_auto_rebase_failure", persistence),
    ("_park_dirty_auto_rebase", guards),
    ("_park_dirty_recovery", outcomes),
    ("_park_diverged_recovery", outcomes),
    ("_park_failed_auto_rebase_push", guards),
    ("_park_failed_recovery_push", outcomes),
    ("_park_unreadable_post_rebase_head", guards),
    ("_park_unreadable_pre_rebase_head", startup),
    ("_post_auto_rebase_notice", publication),
    ("_post_recovered_rebase_notice", persistence),
    ("_prepare_recovered_rebase_state", persistence),
    ("_publish_auto_rebase", publication),
    ("_publish_auto_rebase_from_pr", pr),
    ("_pushed_recovery_notice", outcomes),
    ("_read_remote_recovery_head", snapshot),
    ("_rebase_base_into_worktree", pre_pr),
    ("_rebase_in_progress", pre_pr),
    ("_rebase_state_exists", pre_pr),
    ("_recover_pending_auto_base_rebase", recovery),
    ("_recover_pending_auto_base_rebase_context", recovery),
    ("_record_auto_rebase_attempt", startup),
    ("_refresh_base_and_worktrees", refresh),
    ("_reject_unknown_recovery_comparison", outcomes),
    ("_reset_clear_and_park", persistence),
    ("_retry_recovery_push", recovery),
    ("_route_pr_worktree_conflict_context", conflicts),
    ("_route_pr_worktree_to_resolving_conflict", conflicts),
    ("_route_recovered_rebase", persistence),
    ("_route_recovery_snapshot", recovery),
    ("_start_auto_rebase", startup),
    ("_sync_discovered_worktree", refresh),
    ("_sync_pr_worktree_context", pr),
    ("_sync_pr_worktree_to_base", pr),
    ("_sync_pre_pr_worktree", pre_pr),
    ("_sync_worktree_with_base", refresh),
    ("_worktree_behind_base", refresh),
    ("log", state),
)


def _imported_orchestrator_modules(module: str) -> list[str]:
    """Names of the orchestrator modules a fresh `import module` pulls in."""
    completed = subprocess.run(
        [sys.executable, "-c", _LAYERING_SCRIPT.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.split()


class CleanProcessImportTest(unittest.TestCase):
    """Each base-sync module imports standalone in a fresh interpreter.

    The owners bind their collaborators at import time while the `base_sync`
    facade resolves them lazily, so importing any one of them first must not
    need a name a half-run module has not defined yet. A subprocess per module
    gives each a clean `sys.modules` no other test has already populated,
    exposing an import-order cycle a facade-first suite run would mask.
    """

    def test_each_module_imports_standalone(self) -> None:
        for module in _MODULES:
            with self.subTest(module=module):
                completed = subprocess.run(
                    [sys.executable, "-c", f"import {module}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)


class LayeringTest(unittest.TestCase):
    """The owners import nothing from the base-sync leaves or above them."""

    def test_lower_owners_stay_in_their_layer(self) -> None:
        for owner, allowed_roots in _ALLOWED_ROOTS:
            with self.subTest(module=owner):
                for imported in _imported_orchestrator_modules(owner):
                    self.assertTrue(
                        self._within_layers(imported, allowed_roots),
                        f"{owner} reaches past its layer via {imported}",
                    )

    def test_owners_stay_below_base_sync_leaves(self) -> None:
        for module in _OWNERS:
            with self.subTest(module=module):
                for imported in _imported_orchestrator_modules(module):
                    self.assertFalse(
                        imported.startswith(_FORBIDDEN_PREFIXES),
                        f"{module} inverts the dependency via {imported}",
                    )

    def _within_layers(self, imported: str, allowed_roots: tuple) -> bool:
        if imported in _ALLOWED_MODULES:
            return True
        return any(
            imported == root or imported.startswith(f"{root}.")
            for root in allowed_roots
        )


class PackageSurfaceTest(unittest.TestCase):
    """The initializer carries no bindings; `base_sync` forwards to owners."""

    def test_no_flat_implementation_leaf_survives(self) -> None:
        # Every behavior now has an owner in the package, so a flat module
        # beyond the two compatibility hooks would be base sync re-flattening
        # itself back onto the facade it is meant to be reachable through.
        flat_layer = Path(base_sync.__file__).parent
        flat_modules = {
            leaf.name for leaf in flat_layer.glob("_base_sync_*.py")
        }
        self.assertEqual(flat_modules, _COMPATIBILITY_LEAVES)

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name):
                with self.assertRaises(AttributeError):
                    getattr(git.base_sync, owner_only_name)

    def test_facade_resolves_owner_objects(self) -> None:
        # The facade forwards rather than rebuilding, so a leaf reading a
        # context class or a pinned-state key off `base_sync` -- and the
        # patches aimed at that facade -- see the owner's definition.
        for export_name, owner in _FACADE_FORWARDS:
            with self.subTest(name=export_name):
                self.assertIs(
                    getattr(base_sync, export_name),
                    getattr(owner, export_name),
                )


if __name__ == "__main__":
    unittest.main()
