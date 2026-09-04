# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Clean-process import, package-surface, and inventory checks for the worktrees owners."""

from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module
from importlib.util import find_spec

from orchestrator.git import worktrees as _worktrees_package

# The artifact scan's own owners, the classification over it, and the
# maintenance pass that spends one, named apart from the lifecycle ones above
# because that is the split the map draws: only the last of them writes.
from orchestrator.git.worktrees import (
    attribution,
    claims,
    cleanup,
    creation,
    decomposition,
    discovery,
    eligibility,
    evidence,
    inventory,
    maintenance,
    models,
    paths,
    probes,
    reclaim,
    recovery,
    terminal,
)
from tests.git.inventory_test_support import inventory_modules

_PACKAGE = "orchestrator"

# The spelling that answers as a logger and nowhere else: nothing resolves at
# it as a module and no inventory in the package may name it as the module a
# hub reads a name off, but it is still the channel the owners report on.
_LIFECYCLE_SPELLING = "orchestrator.worktree_lifecycle"

# The aggregate spelling over every git domain at once, held to the same rule
# minus the logger.
_AGGREGATE_HUB = "orchestrator.worktrees"

_ABSENT_TARGETS = (_AGGREGATE_HUB, _LIFECYCLE_SPELLING)

_MODULES = (
    "orchestrator.git.worktrees",
    "orchestrator.git.worktrees.attribution",
    "orchestrator.git.worktrees.claims",
    "orchestrator.git.worktrees.cleanup",
    "orchestrator.git.worktrees.creation",
    "orchestrator.git.worktrees.decomposition",
    "orchestrator.git.worktrees.discovery",
    "orchestrator.git.worktrees.eligibility",
    "orchestrator.git.worktrees.evidence",
    "orchestrator.git.worktrees.inventory",
    "orchestrator.git.worktrees.maintenance",
    "orchestrator.git.worktrees.models",
    "orchestrator.git.worktrees.paths",
    "orchestrator.git.worktrees.probes",
    "orchestrator.git.worktrees.reclaim",
    "orchestrator.git.worktrees.recovery",
    "orchestrator.git.worktrees.terminal",
)

# The module paths a second import site for these owners would take: the two
# spellings themselves, and the inventory and resolver hooks either one would
# be built from.
_FLAT_MODULES = (
    "orchestrator._worktree_lifecycle_export_manifest",
    "orchestrator._worktree_lifecycle_exports",
    "orchestrator._worktrees_export_manifest",
    "orchestrator._worktrees_exports",
    _AGGREGATE_HUB,
    _LIFECYCLE_SPELLING,
)

# The initializer binds nothing, so each name answers on the owner that defines
# it, never on the package itself.
_OWNER_ONLY_NAMES = (
    "ArtifactInventory",
    "ArtifactVerdict",
    "IssueArtifacts",
    "MaintenanceResult",
    "RetentionReason",
    "_branch_has_unpushed_commits",
    "_branch_name",
    "_checkout_identity",
    "_classify_artifacts",
    "_cleanup_terminal_branch",
    "_ensure_worktree",
    "_decompose_worktree_path",
    "_local_issue_inventory",
    "_maintained_candidates",
    "_maintenance_candidates",
    "_remove_issue_worktree",
    "_resolve_branch_name",
    "_sanitize_slug",
    "_terminal_retentions",
    "_worktree_path",
)

# Every name the owners define, paired with the owner that defines it: the slug
# pattern and the digest math behind it, the two sanitizers, the branch, root,
# and worktree-path derivations, the pinned / legacy resolver and the
# `issue-<n>` read that runs back the other way, the two checkout paths one
# issue can have been checked out at, the
# candidate-branch and commit-count reads behind the unpushed-commit probe, the
# two creators, the new-commit probe, the reported fetch and the start point a
# restore picks, the handoff anchor with the target choice, the ref move, and the
# revision read under it, and the `worktree` argv they run, the
# decomposer's path, creation, and removal, the per-issue removal and local
# branch deletion, the two teardowns composed from them, and the local artifact
# scan: the two records it answers with, the branch listing and checkout reads
# under it, the attribution rules for a branch and for a checkout directory,
# the clone resolution, the grouping over it and the shape that grouping
# takes, the flat pre-namespacing checkouts, the identity read that says which
# clone each is a worktree of, the rule that turns it into every claimant, and
# the record filing what one repository holds apart from what it may not touch,
# and the per-clone, per-repository, and per-issue assembly. Then the
# classification over what that scan found: the three-answer probe vocabulary,
# the two records a verdict is made of and the commit it hands over when it
# clears one, the nine fail-closed reads -- the ignored-path one that answers
# for what a status leaves out, and the one asking when a tree was last
# disturbed, over the checkout's own git directory and the two files in it a
# commit rewrites, and the one asking which branches a tree of the clone is
# standing on -- and the two runners under them,
# the issue, pinned-state, and pull-request reads
# GitHub answers with and the boundaries around each of them, and the
# composition that turns both into one verdict per candidate, with the
# checkout's own three-read order, the tables each of those is charged
# through, the tip read that falls back to the remote, the HEAD read spent
# twice, and the proof an eligible verdict is handed over as. Then the pass
# that spends one of those verdicts: the remote listing and its namespace
# pattern, the attribution and grouping over it, the layout reading and the
# merge that widens one candidate, the whole discovery over both halves, the
# three commit-pinned teardown steps and the argv each runs, and the pass
# itself -- the injected guard's type, the quiet period, the reason-to-outcome
# table, and every gate, step, and answer between them. Naming the whole
# surface makes a helper added to an owner an edit here rather than a
# definition site nothing checks.
_OWNER_DEFINED = (
    ("ActivityGuard", maintenance),
    ("ArtifactInventory", models),
    ("ArtifactVerdict", models),
    ("AttributedIssues", attribution),
    ("BranchTip", models),
    ("CandidateKey", discovery),
    ("CandidateLayout", models),
    ("CloneGroups", inventory),
    ("IssueArtifacts", models),
    ("IssueBranches", attribution),
    ("IssueNumbers", inventory),
    ("LegacyCheckouts", inventory),
    ("MaintenanceCandidate", models),
    ("MaintenanceOutcome", models),
    ("MaintenanceReason", models),
    ("MaintenanceResult", models),
    ("MaintenanceScan", models),
    ("ProbeAnswer", models),
    ("ProvenTip", models),
    ("PublishedBranches", discovery),
    ("Retention", models),
    ("RetentionReason", models),
    ("TERMINAL_LABELS", claims),
    ("_CLEANLINESS_REASONS", eligibility),
    ("_CheckoutReads", eligibility),
    ("_GIT_NEGATIVE", evidence),
    ("_HEAD", evidence),
    ("_HEAD_REFLOG", evidence),
    ("_HIDDEN_REASONS", eligibility),
    ("_IDENTITY_REASONS", eligibility),
    ("_INDEX", evidence),
    ("_ISSUE_SEGMENT_RE", paths),
    ("_LISTED", attribution),
    ("_LOCAL_BRANCH_PREFIX", probes),
    ("_LOCAL_REF_PREFIX", evidence),
    ("_LOCAL_REF_PREFIX", reclaim),
    ("_OPEN_PULL_REQUEST", claims),
    ("_ORCHESTRATOR_BRANCH_REFS", probes),
    ("_ORCHESTRATOR_REMOTE_REFS", discovery),
    ("_OUTCOMES", maintenance),
    ("_QUIET_PERIOD_SECONDS", maintenance),
    ("_REF_DELETE", reclaim),
    ("_REF_SEPARATOR", attribution),
    ("_REMOTE_BRANCH_PREFIX", discovery),
    ("_SAFE_CHAR", paths),
    ("_SLUG_DIGEST_LEN", paths),
    ("_SLUG_SAFE_RE", paths),
    ("_VERIFY_QUIETLY", evidence),
    ("_VERIFY_REF", creation),
    ("_WORKTREE_ADD", creation),
    ("_WORKTREE_BRANCH", evidence),
    ("_WORKTREE_REMOVE", reclaim),
    ("_WORKTREE_REMOVE_FORCE", creation),
    ("_activity_reason", maintenance),
    ("_anchor_pr_worktree", creation),
    ("_anchor_target", creation),
    ("_answered", maintenance),
    ("_artifact_reading", eligibility),
    ("_artifact_verdict", eligibility),
    ("_attributed_issues", attribution),
    ("_attributed_legacy", inventory),
    ("_base_contains", evidence),
    ("_branch_attribution", attribution),
    ("_branch_commit_count", recovery),
    ("_branch_has_unpushed_commits", recovery),
    ("_branch_name", paths),
    ("_branch_reasons", eligibility),
    ("_branch_retentions", eligibility),
    ("_branch_tip", eligibility),
    ("_candidate_issue_branches", recovery),
    ("_candidate_keys", discovery),
    ("_candidate_layout", discovery),
    ("_candidate_order", discovery),
    ("_carrying_pull_request", claims),
    ("_checked_out_branches", evidence),
    ("_checkout_clone", probes),
    ("_checkout_entries", probes),
    ("_checkout_git_dir", evidence),
    ("_checkout_head", eligibility),
    ("_checkout_identity", evidence),
    ("_checkout_numbers", probes),
    ("_checkout_reading", eligibility),
    ("_checkout_reason", eligibility),
    ("_checkout_retentions", eligibility),
    ("_checkout_stop", maintenance),
    ("_checkout_tip", evidence),
    ("_checkout_tip_retentions", eligibility),
    ("_claim_reason", maintenance),
    ("_classified_candidates", eligibility),
    ("_classify_artifacts", eligibility),
    ("_clean_worktree", evidence),
    ("_cleanup_decompose_worktree", decomposition),
    ("_cleanup_question_worktree", terminal),
    ("_cleanup_terminal_branch", terminal),
    ("_cleared_tips", maintenance),
    ("_clone_read", evidence),
    ("_colliding_worktree_slugs", attribution),
    ("_commit_accounting", claims),
    ("_commit_count_from_stdout", recovery),
    ("_countable_legacy_checkouts", attribution),
    ("_current_names", discovery),
    ("_decompose_worktree_path", decomposition),
    ("_delete_local_issue_branch", cleanup),
    ("_delete_local_ref_at", reclaim),
    ("_delete_remote_branch_at", reclaim),
    ("_ended_retentions", claims),
    ("_ensure_decompose_worktree", decomposition),
    ("_ensure_pr_worktree", creation),
    ("_ensure_worktree", creation),
    ("_fetch_for_restore", creation),
    ("_fetched_issue", claims),
    ("_file_claimants", inventory),
    ("_group_published", discovery),
    ("_hardened_read", evidence),
    ("_has_new_commits", creation),
    ("_head_is_own_branch", evidence),
    ("_head_ref", evidence),
    ("_held_checkouts", inventory),
    ("_issue_artifacts", inventory),
    ("_issue_checkout_number", probes),
    ("_issue_segment_number", paths),
    ("_issue_worktree_paths", paths),
    ("_kept_subject", maintenance),
    ("_keyed_candidate", discovery),
    ("_last_touched", evidence),
    ("_legacy_checkout_claimants", attribution),
    ("_legacy_checkout_numbers", probes),
    ("_legacy_claimants", inventory),
    ("_legacy_names", discovery),
    ("_legacy_worktree_path", paths),
    ("_local_branch_tip", evidence),
    ("_local_issue_inventory", inventory),
    ("_local_orchestrator_branches", probes),
    ("_maintained_candidate", maintenance),
    ("_maintained_candidates", maintenance),
    ("_maintenance_candidates", discovery),
    ("_matching_owners", attribution),
    ("_merged", inventory),
    ("_move_branch_onto", creation),
    ("_nothing_ignored", evidence),
    ("_open_pull_request_retentions", claims),
    ("_pr_branch_start_point", creation),
    ("_proven_tips", eligibility),
    ("_published_branches", discovery),
    ("_published_tip", evidence),
    ("_quiet_checkout", evidence),
    ("_read_artifacts", eligibility),
    ("_read_orchestrator_refs", probes),
    ("_read_state", claims),
    ("_reclaimed", maintenance),
    ("_record_attribution", attribution),
    ("_recorded_pull_request", claims),
    ("_remote_half", discovery),
    ("_remote_issue_branches", discovery),
    ("_remote_orchestrator_branches", discovery),
    ("_remove_issue_worktree", cleanup),
    ("_remove_recognized_worktree", reclaim),
    ("_repo_worktrees_root", paths),
    ("_resolve_branch_name", paths),
    ("_resolved_commit", creation),
    ("_resolved_root", inventory),
    ("_resolved_tip", evidence),
    ("_root_inventory", inventory),
    ("_run_decompose_worktree_removal", decomposition),
    ("_run_issue_worktree_removal", cleanup),
    ("_run_local_branch_deletion", cleanup),
    ("_sanitize_branch_segment", paths),
    ("_sanitize_slug", paths),
    ("_scanned", inventory),
    ("_shared_repository", evidence),
    ("_slug_digest", paths),
    ("_slugs_by_worktrees_root", attribution),
    ("_spec_inventory", inventory),
    ("_specs_by_clone", inventory),
    ("_still_there", reclaim),
    ("_take_branch", maintenance),
    ("_take_branches", maintenance),
    ("_take_checkout", maintenance),
    ("_take_checkouts", maintenance),
    ("_take_local_branch", maintenance),
    ("_take_remote_branch", maintenance),
    ("_terminal_retentions", claims),
    ("_tip_retentions", eligibility),
    ("_widened", discovery),
    ("_workflow_members", claims),
    ("_worktree_issue_numbers", probes),
    ("_worktree_path", paths),
)

# The owners that report, each binding the channel an operator's level and
# handler selection is keyed on.
_REPORTING_OWNERS = (
    attribution, claims, cleanup, creation, decomposition, discovery,
    evidence, inventory, maintenance, probes, reclaim, terminal,
)


class CleanProcessImportTest(unittest.TestCase):
    """Each owner imports standalone in a fresh interpreter.

    Every owner depends only on config, pinned state, the git command /
    lock / branch-transport owners, and its in-package siblings, so importing
    any one of them first must not need a name a half-run module has not
    defined yet. A subprocess per module gives each a clean `sys.modules` no
    other test has already populated, exposing an import-order cycle a
    package-first suite run would mask.
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


class PackageSurfaceTest(unittest.TestCase):
    """The initializer binds nothing and every name answers on its owner."""

    def test_initializer_exposes_no_owner_names(self) -> None:
        for owner_only_name in _OWNER_ONLY_NAMES:
            with self.subTest(name=owner_only_name), self.assertRaises(AttributeError):
                getattr(_worktrees_package, owner_only_name)

    def test_every_name_is_defined_on_its_owner(self) -> None:
        # A helper lifted onto a sibling would still resolve for its callers,
        # so the defining module is what a patch aimed at the teardown ordering
        # or the digest math behind a slug has to land on.
        for owner_name, owner in _OWNER_DEFINED:
            with self.subTest(name=owner_name):
                self.assertIn(owner_name, owner.__dict__)


class OwnerImportSiteTest(unittest.TestCase):
    """No surface over these owners sits beside them."""

    def test_no_flat_module_exists(self) -> None:
        # Anything importable at these paths would be a second identity for the
        # branch and path derivations every worktree is created and torn down
        # by -- free to drift from the owner silently and invisible to a patch
        # aimed at it. Resolving the spec rather than stat-ing one path catches
        # a copy planted anywhere the interpreter would find it.
        for module in _FLAT_MODULES:
            with self.subTest(module=module):
                self.assertIsNone(find_spec(module))

    def test_no_inventory_targets_an_absent_spelling(self) -> None:
        # Nothing resolves at either spelling, so an inventory naming one is a
        # dead target that stays quiet until whichever caller reads that name
        # runs. Scanning every inventory in the package is what surfaces it
        # before then.
        for inventory_name in inventory_modules(_PACKAGE):
            inventory = import_module(inventory_name)
            targets = {target.module_name for target in inventory.EXPORTS}
            for absent in _ABSENT_TARGETS:
                with self.subTest(inventory=inventory_name, target=absent):
                    self.assertNotIn(absent, targets)


class ReportingChannelTest(unittest.TestCase):
    """Every owner that logs reports on the operator-facing channel.

    Operators filter on the rendered prefix and attach handlers to it, so a
    logger renamed after its own module path would silently drop that
    owner's worktree and branch teardown lines out of their filters.
    """

    def test_owners_keep_the_operator_name(self) -> None:
        for owner in _REPORTING_OWNERS:
            with self.subTest(owner=owner.__name__):
                self.assertEqual(owner.log.name, _LIFECYCLE_SPELLING)


if __name__ == "__main__":
    unittest.main()
