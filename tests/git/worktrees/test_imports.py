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

# Every owner the package defines: the worktree lifecycle ones, the read-only
# scan and the classification over it, and the teardown that spends one of
# that classification's verdicts -- the only one of them that writes, and the
# ledger beside it that it writes its own notes to itself into.
from orchestrator.git.worktrees import (
    attribution,
    claims,
    cleanup,
    creation,
    decomposition,
    eligibility,
    evidence,
    inventory,
    models,
    obligations,
    paths,
    probes,
    reclamation,
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
    "orchestrator.git.worktrees.eligibility",
    "orchestrator.git.worktrees.evidence",
    "orchestrator.git.worktrees.inventory",
    "orchestrator.git.worktrees.models",
    "orchestrator.git.worktrees.obligations",
    "orchestrator.git.worktrees.paths",
    "orchestrator.git.worktrees.probes",
    "orchestrator.git.worktrees.reclamation",
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
    "ArtifactReclamation",
    "ArtifactVerdict",
    "IssueArtifacts",
    "RetentionReason",
    "_branch_has_unpushed_commits",
    "_branch_name",
    "_checkout_identity",
    "_classify_artifacts",
    "_cleanup_terminal_branch",
    "_ensure_worktree",
    "_decompose_worktree_path",
    "_local_issue_inventory",
    "_reclaim_artifacts",
    "_reclaim_recorded_notes",
    "_recorded_obligations",
    "_remove_issue_worktree",
    "_resolve_branch_name",
    "_sanitize_slug",
    "_terminal_retentions",
    "_worktree_path",
)

# Every name the owners define, paired with the owner that defines it: the slug
# pattern and the digest math behind it, the two sanitizers, the branch, root,
# and worktree-path derivations, the pinned / legacy resolver and the
# `issue-<n>` read that runs back the other way, the
# candidate-branch and commit-count reads behind the unpushed-commit probe, the
# two creators, the new-commit probe, the reported fetch and the start point a
# restore picks, the handoff anchor with the target choice, the ref move, and the
# revision read under it, and the `worktree` argv they run, the
# decomposer's path, creation, and removal, the per-issue removal and local
# branch deletion, the two teardowns composed from them, and the local artifact
# scan: the two records it answers with, the branch listing and checkout reads
# under it, the attribution rules for a branch and for a checkout directory,
# the clone resolution, the grouping over it and the shape that grouping
# takes, and the per-clone, per-repository, and per-issue assembly. Then the
# classification over what that scan found: the three-answer probe vocabulary
# and the two records a verdict is made of, the eight fail-closed reads -- the
# ignored-path one that answers for what a status leaves out, the object-store
# one and the peel that makes it go there among them -- and the
# three runners under them, the clone-side revision read the last of those
# shares included, the issue, pinned-state, and pull-request reads
# GitHub answers with and the boundaries around each of them, and the
# composition that turns both into one verdict per candidate, with the
# checkout's own three-read order and the tables each of those is charged
# through. Then the
# teardown that spends one: the surfaces a candidate is taken from and what
# each was left in, the checkout's presence, ownership, and revalidation
# reads, the two lease-pinned deletions and the boundaries around them, the
# live-checkout and symbolic-ref reads the local one is refused by, the
# `worktree list` spellings and the undereferenced argv they are written in,
# the second readings a refused deletion is told apart by on either host and
# the one taken after a deletion that landed, with the restore it leads to,
# the gates ordering the three and what each of them is kept for once the
# branch has been asked about again, what a verdict clearing no commit for a
# branch leaves, the line an unfindable leftover is reported on, and the pass
# that
# finishes what an earlier one wrote down, over both kinds of note -- the
# records with their classification, the fetch that puts a commit only the
# remote has within reach of one, and the commit it clears now; then the
# anchors, each measured against whatever would still name what it holds -- the
# base, and then the pull requests that account for work no base ever carries
# -- and the branch put back where the scan reads its candidates from when the
# ledger will take no note at all -- with the ledger under it: the namespace,
# the
# repository's own key and the room it opens, the ref one branch is recorded
# at, the write and the delete every note goes through, the value a record
# carries when nothing was cleared and the reminder written at it, the
# read-back and the parse beneath it, the discharge, and the anchor a removal
# pins what it is about to take under -- its namespace, its ref, its write,
# its read-back and the three-answer resolution under it -- the value a name
# nothing is at comes back as among them -- the status a read of one that is
# not there answers with, its
# discard, the room it opens and the segment it names an issue by, the lease
# that only ever creates one, and the
# git directory, the locks that keep a checkout still while it comes down --
# its own two and the one git takes for the branch under its HEAD -- the
# exclusive creation each is taken by, the held removal itself, the readings
# retaken one process before it and the comparison telling a path that IS a
# tree from one that merely leads to it, the registration held still while the
# removal aims by it and the mode change either side of that, the last word on
# whether the path named is gone, the reading that tells a prunable
# registration naming nothing from one naming a tree still there, the branch
# written back where the scan reads its candidates from and the two callers
# that reach for it, and the take, the discard, and the reconciliation of a
# note an earlier pass left standing --
# and the second reading a refused branch deletion is told apart by. Naming
# the whole surface makes a helper added to an owner an edit here rather than
# a definition site nothing checks.
_OWNER_DEFINED = (
    ("ANCHOR_NAMESPACE", obligations),
    ("ArtifactInventory", models),
    ("ArtifactReclamation", models),
    ("ArtifactSurface", models),
    ("ArtifactVerdict", models),
    ("AttributedIssues", attribution),
    ("BranchTip", models),
    ("CloneGroups", inventory),
    ("IssueArtifacts", models),
    ("IssueBranches", attribution),
    ("ProbeAnswer", models),
    ("ProvenTip", models),
    ("RECLAIM_NAMESPACE", obligations),
    ("Retention", models),
    ("RetentionReason", models),
    ("SurfaceOutcome", models),
    ("SurfaceResult", models),
    ("TERMINAL_LABELS", claims),
    ("_ABSENT_LEASE", obligations),
    ("_BRANCH_REF_PREFIX", reclamation),
    ("_CHECKOUT_LOCKS", reclamation),
    ("_CHECKOUT_STANDING", reclamation),
    ("_CLEANLINESS_REASONS", eligibility),
    ("_CLONE", reclamation),
    ("_COMMIT_PEEL", evidence),
    ("_DIGEST_MARK", obligations),
    ("_GIT_NEGATIVE", evidence),
    ("_GIT_NO_SUCH_REF", obligations),
    ("_GIT_NOT_SYMBOLIC", reclamation),
    ("_HEAD", evidence),
    ("_HEAD", obligations),
    ("_HIDDEN_REASONS", eligibility),
    ("_IDENTITY_REASONS", eligibility),
    ("_ISSUE_SEGMENT", obligations),
    ("_ISSUE_SEGMENT_RE", paths),
    ("_LOCAL_BRANCH_PREFIX", probes),
    ("_LOCAL_REF_PREFIX", evidence),
    ("_NO_NOTE", obligations),
    ("_NO_DEREF", obligations),
    ("_NO_DEREF", reclamation),
    ("_ON_BRANCH", reclamation),
    ("_OPEN_PULL_REQUEST", claims),
    ("_ORCHESTRATOR_BRANCH_REFS", probes),
    ("_PRUNABLE", reclamation),
    ("_RECORD_FIELDS", obligations),
    ("_RECORD_FORMAT", obligations),
    ("_REF_SEPARATOR", attribution),
    ("_REGISTRATION", reclamation),
    ("_REMINDER_MARK", obligations),
    ("_REF_LOCK", reclamation),
    ("_REMOTE", reclamation),
    ("_REMOTE_STANDING", reclamation),
    ("_SAFE_CHAR", paths),
    ("_SLUG_DIGEST_LEN", paths),
    ("_SLUG_SAFE_RE", paths),
    ("_VERIFY_QUIETLY", evidence),
    ("_VERIFY_REF", creation),
    ("_WORKTREE_ADD", creation),
    ("_WORKTREE_ENTRY", reclamation),
    ("_WORKTREE_REMOVE_FORCE", creation),
    ("_WRITABLE", reclamation),
    ("_anchor_accounted", reclamation),
    ("_anchor_checkout", obligations),
    ("_anchor_let_go", reclamation),
    ("_anchor_pr_worktree", creation),
    ("_anchor_ref", obligations),
    ("_anchor_settled", reclamation),
    ("_anchor_target", creation),
    ("_anchor_taken", reclamation),
    ("_anchors_prefix", obligations),
    ("_anchored_commit", obligations),
    ("_anchored_removal", reclamation),
    ("_artifact_reading", eligibility),
    ("_artifact_verdict", eligibility),
    ("_attributed_issues", attribution),
    ("_base_contains", evidence),
    ("_branch_attribution", attribution),
    ("_branch_commit_count", recovery),
    ("_branch_has_unpushed_commits", recovery),
    ("_branch_name", paths),
    ("_branch_reasons", eligibility),
    ("_branch_ref", reclamation),
    ("_branch_restored", reclamation),
    ("_branch_retentions", eligibility),
    ("_branch_surfaces", reclamation),
    ("_branch_tip", eligibility),
    ("_came_down", reclamation),
    ("_candidate_issue_branches", recovery),
    ("_carries_commit", evidence),
    ("_carrying_pull_request", claims),
    ("_checkout_entries", probes),
    ("_checkout_gitdir", reclamation),
    ("_checkout_head", eligibility),
    ("_checkout_identity", evidence),
    ("_checkout_locks", reclamation),
    ("_checkout_present", reclamation),
    ("_checkout_reason", eligibility),
    ("_checkout_retentions", eligibility),
    ("_checkout_tip", evidence),
    ("_checkout_tip_retentions", eligibility),
    ("_checkouts_holding", reclamation),
    ("_classified_candidates", eligibility),
    ("_classify_artifacts", eligibility),
    ("_clean_worktree", evidence),
    ("_cleanup_decompose_worktree", decomposition),
    ("_cleanup_question_worktree", terminal),
    ("_cleanup_terminal_branch", terminal),
    ("_cleared_tip", reclamation),
    ("_clone_read", evidence),
    ("_colliding_worktree_slugs", attribution),
    ("_commit_accounting", claims),
    ("_commit_count_from_stdout", recovery),
    ("_common_git_dir", evidence),
    ("_decompose_worktree_path", decomposition),
    ("_delete_local_issue_branch", cleanup),
    ("_deleted_local_branch", reclamation),
    ("_deleted_remote_branch", reclamation),
    ("_deletion_stood", reclamation),
    ("_discard_anchor", obligations),
    ("_discharge_obligation", obligations),
    ("_discharged", reclamation),
    ("_dropped_note", obligations),
    ("_ended_retentions", claims),
    ("_ensure_decompose_worktree", decomposition),
    ("_ensure_pr_worktree", creation),
    ("_ensure_worktree", creation),
    ("_fetch_for_restore", creation),
    ("_fetched_issue", claims),
    ("_hardened_read", evidence),
    ("_has_new_commits", creation),
    ("_head_is_own_branch", evidence),
    ("_head_ref", evidence),
    ("_held_still", reclamation),
    ("_holding_nothing", reclamation),
    ("_issue_artifacts", inventory),
    ("_issue_checkout_number", probes),
    ("_issue_segment_number", paths),
    ("_kept_local", reclamation),
    ("_let_go", reclamation),
    ("_local_branch_tip", evidence),
    ("_local_issue_inventory", inventory),
    ("_local_orchestrator_branches", probes),
    ("_made_read_only", reclamation),
    ("_marked_again", reclamation),
    ("_marked_at", reclamation),
    ("_matching_owners", attribution),
    ("_merged", inventory),
    ("_move_branch_onto", creation),
    ("_nothing_ignored", evidence),
    ("_note_at", obligations),
    ("_obligation_ref", obligations),
    ("_one_directory", reclamation),
    ("_open_pull_request_retentions", claims),
    ("_owed_issue", reclamation),
    ("_parsed_records", obligations),
    ("_pr_branch_start_point", creation),
    ("_pruned_away", reclamation),
    ("_proven_tips", eligibility),
    ("_published_tip", evidence),
    ("_read_orchestrator_refs", probes),
    ("_put_back", reclamation),
    ("_read_notes", obligations),
    ("_read_state", claims),
    ("_ready_to_go", reclamation),
    ("_reclaim_artifacts", reclamation),
    ("_reclaim_recorded_notes", reclamation),
    ("_reclaimed_anchor", reclamation),
    ("_reclaimed_anchors", reclamation),
    ("_reclaimed_branch", reclamation),
    ("_reclaimed_checkout", reclamation),
    ("_reclaimed_local_branch", reclamation),
    ("_reclaimed_record", reclamation),
    ("_reclaimed_records", reclamation),
    ("_reclaimed_remote_branch", reclamation),
    ("_record_attribution", attribution),
    ("_record_obligation", obligations),
    ("_recorded_deletion", reclamation),
    ("_recorded_anchors", obligations),
    ("_recorded_notes", obligations),
    ("_recorded_obligations", obligations),
    ("_recorded_pull_request", claims),
    ("_records_prefix", obligations),
    ("_refused_delete", reclamation),
    ("_refused_push", reclamation),
    ("_remind", obligations),
    ("_registration_frozen", reclamation),
    ("_reminded", reclamation),
    ("_removal_under_lock", reclamation),
    ("_removal_while_held", reclamation),
    ("_remove_issue_worktree", cleanup),
    ("_removed_checkout", reclamation),
    ("_repo_worktrees_root", paths),
    ("_reported", reclamation),
    ("_repository_key", obligations),
    ("_resolve_branch_name", paths),
    ("_resolved_commit", creation),
    ("_resolved_root", inventory),
    ("_resolved_tip", evidence),
    ("_revision_read", evidence),
    ("_root_inventory", inventory),
    ("_run_decompose_worktree_removal", decomposition),
    ("_run_issue_worktree_removal", cleanup),
    ("_run_local_branch_deletion", cleanup),
    ("_same_object", reclamation),
    ("_same_place", reclamation),
    ("_sanitize_branch_segment", paths),
    ("_sanitize_slug", paths),
    ("_shared_repository", evidence),
    ("_slug_digest", paths),
    ("_slugs_by_worktrees_root", attribution),
    ("_spec_inventory", inventory),
    ("_specs_by_clone", inventory),
    ("_spent_anchor_cleared", reclamation),
    ("_standing_on", reclamation),
    ("_still_cleared", reclamation),
    ("_stranded", reclamation),
    ("_still_ours", reclamation),
    ("_symbolic_branch", reclamation),
    ("_taken_exclusively", reclamation),
    ("_terminal_retentions", claims),
    ("_thawed", reclamation),
    ("_tip_retentions", eligibility),
    ("_unmoved", reclamation),
    ("_unproven_remote", reclamation),
    ("_unresolved", reclamation),
    ("_untouched", reclamation),
    ("_within_reach", reclamation),
    ("_workflow_members", claims),
    ("_worktree_issue_numbers", probes),
    ("_worktree_path", paths),
    ("_written_note", obligations),
)

# The owners that report, each binding the channel an operator's level and
# handler selection is keyed on.
_REPORTING_OWNERS = (
    attribution, claims, cleanup, creation, decomposition, evidence,
    inventory, obligations, probes, reclamation, terminal,
)


class CleanProcessImportTest(unittest.TestCase):
    """Each owner imports standalone in a fresh interpreter.

    Every owner depends only on config, pinned state, the git command /
    lock / authentication owners, and its in-package siblings, so importing
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
