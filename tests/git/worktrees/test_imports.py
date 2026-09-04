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

# The artifact scan's own owners and the classification over it, named apart
# from the lifecycle ones above because that is the split the map draws: those
# seven are read-only. The teardown that spends one of that classification's
# verdicts is the one owner here that destroys anything, and the ledger beside
# it writes only the notes this host keeps for itself.
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
# classification over what that scan found: the three-answer probe vocabulary,
# the two records a verdict is made of and the commit it hands over when it
# clears one, the seven fail-closed reads -- the ignored-path one that answers
# for what a status leaves out among them -- and the two runners under them,
# the issue, pinned-state, and pull-request reads
# GitHub answers with and the boundaries around each of them, and the
# composition that turns both into one verdict per candidate, with the
# checkout's own three-read order, the tables each of those is charged
# through, the tip read that falls back to the remote, the HEAD read spent
# twice, and the proof an eligible verdict is handed over as. Then the four
# records a teardown over one of those verdicts answers in, and the ledger it
# writes its own notes to itself into: the two namespaces, the repository's own
# key and the room each namespace opens for it, the ref one branch is recorded
# at, the write and the delete every note goes through, the value a record
# carries when nothing was cleared and the reminder written at it, the
# discharge, the read-back with the separator it is split on and the whole-line
# and per-line parses beneath it, and the anchor a removal pins what it is
# about to take under -- its ref, the segment it names an issue by, the lease
# that only ever creates one, the HEAD it is written at, its read-back and the
# three-answer resolution under it, the undereferenced reading that resolution
# and every deletion are gated on with the status a name holding no symbolic
# ref answers at, the value a name nothing is at comes back as and the status
# git answers one with, its discard, and the check that the listing named
# every note the store is holding -- the ref store it is asked of, the names
# the loose half of that store carries, the suffix a write in flight is
# skipped by, the no-follow look that walks a name a room at a time, the rooms
# alone that a write is held to, the two halves of the walk that finds them,
# the one name the lock every reading and every writing is paired under is
# taken by, the check that a write lands in the store this repository reads,
# what tells a value a note under one namespace is written at from a blob, a
# stray tree, an id nothing was written under, or the reminder mark under the
# room that has nothing to say with it -- the object kind a tree answers with,
# the one kind every note carries, and the room the mark is allowed in -- the
# same reading a write is held to before it reports a note kept, and the one
# environment setting that keeps each of those local. Then the teardown that
# spends one of those verdicts on the checkout it cleared: the entry a
# candidate is handed to and the line every deletion is said out loud on, what
# a verdict keeping its candidate is answered with, the removal and the
# boundary around it, the presence read that tells a path that is gone from
# one nobody could answer for, the whole verdict's worth of readings retaken
# one process before the removal -- the derived path, the identity, the tip,
# and the two tree reads that tell what is carried from what is hidden -- and
# the shape everything the removal runs under is carried in. Then the git
# directory those holds are taken in, the checkout's own two locks and the one
# git takes for the branch under its HEAD -- named in full, and chosen only
# once the first two are held, since a HEAD read before its lock is one that
# can move -- the exclusive creation each is taken by, marked with the process
# that took it so a lock a killed pass left behind is one a later pass tells
# from one a running command holds -- staged whole under a name nothing can
# have planted, with the suffix keeping that name out of every ref listing,
# and then linked to the name it is for, since a lock created before it is
# marked is one an incomplete write leaves unrecognisable -- and the staging
# file dropped however that ended, the bounded no-follow read that says what
# one carries and the parse of the process it names, the reading that asks
# whether a name still carries what this pass wrote, the take that reads what
# it took rather than reading before it takes -- the scratch name it is taken
# to, the move itself, and the link a lock that turned out to be somebody's is
# put back under -- the give-back spent through the same take, and the check
# before the removal that each of them is bound to, asked of every hold at
# once with the command the next thing after it;
# the checkout itself, opened as a directory of its own and held that way, the
# reading that says the path still leads to it, and the one afterwards that
# says nothing links to it any more -- with the count that means -- and the
# whole of taking it out of reach of its own name before the command runs: the
# head that name is made under, the making, the move, the aim the registration
# is given after it, the removal spent where the tree now stands, and the
# put-back a removal that did not take it earns; then the reconciliation the
# pass after a stopped one opens with -- what it finds left aside and whether
# that is a tree at all and whether exactly one of them is, the empty names a
# move that never happened reserved and the taking away of each, the repair
# that points git back at what it put back, and the write bits given to a
# registration a stopped pass left held; the
# registration the removal is aimed by: opened without following or waiting
# and held open across the whole take-over, told whether the descriptor is a
# regular file at all, read for what it says from its first byte and refused
# past its bound, told whether it says this checkout, taken over by a copy of
# this pass's own staged under a name of its own -- written whole, however
# little a write takes at a time, replaced whole where a descriptor is written
# through twice, and dropped however that ended -- and
# renamed into place only while the original still is what it was and still
# says it, read once more AFTER that rename with whatever it displaced written
# back where it stood, held by the mode taken off the object rather than the
# name, put back the same way, and asked once more -- both what the name
# resolves to and what the object says -- whether it still means what it
# meant; the note this host is still pinning when a pass is over, reported
# beside the checkout because it outlives it; the comparison
# telling a path that IS a tree from one that merely leads to it and the
# object identity under it, the last word on whether the path named is gone
# and which of the two ways it got that way, and the take, the discard, and
# the reconciliation of the anchor a removal pins what it is about to take
# under.
# Naming the
# whole surface makes a helper added to an owner an edit here rather than a
# definition site nothing checks.
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
    ("_ASIDE_PREFIX", reclamation),
    ("_BRANCH_REF_PREFIX", reclamation),
    ("_CHECKOUT_GIT_FILE", reclamation),
    ("_CHECKOUT_HANDLE", reclamation),
    ("_CHECKOUT_LOCKS", reclamation),
    ("_CLEANLINESS_REASONS", eligibility),
    ("_COMMIT_OBJECT", obligations),
    ("_DIGEST_MARK", obligations),
    ("_GIT_NEGATIVE", evidence),
    ("_GIT_NO_SUCH_REF", obligations),
    ("_GIT_NOT_SYMBOLIC", obligations),
    ("_HEAD", evidence),
    ("_HEAD", obligations),
    ("_HIDDEN_REASONS", eligibility),
    ("_HeldLock", reclamation),
    ("_Holds", reclamation),
    ("_IDENTITY_REASONS", eligibility),
    ("_ISSUE_SEGMENT", obligations),
    ("_ISSUE_SEGMENT_RE", paths),
    ("_LOCAL_BRANCH_PREFIX", probes),
    ("_LOCAL_REF_PREFIX", evidence),
    ("_LOCK_LIMIT", reclamation),
    ("_LOCK_MARK", reclamation),
    ("_NO_DEREF", obligations),
    ("_NO_LAZY_FETCH", obligations),
    ("_NO_NOTE", obligations),
    ("_OPEN_PULL_REQUEST", claims),
    ("_ORCHESTRATOR_BRANCH_REFS", probes),
    ("_OWNER_WRITE", reclamation),
    ("_RECORD_FIELDS", obligations),
    ("_RECORD_FORMAT", obligations),
    ("_RECORD_SEPARATOR", obligations),
    ("_RECLAIM_ROOM", obligations),
    ("_REF_LOCK", reclamation),
    ("_REF_LOCK_SUFFIX", obligations),
    ("_REF_SEPARATOR", attribution),
    ("_REGISTRATION", reclamation),
    ("_REGISTRATION_LIMIT", reclamation),
    ("_REMINDER_MARK", obligations),
    ("_REPLACED_SUFFIX", reclamation),
    ("_REPLACING", reclamation),
    ("_Registration", reclamation),
    ("_SAFE_CHAR", paths),
    ("_SLUG_DIGEST_LEN", paths),
    ("_SLUG_SAFE_RE", paths),
    ("_STAGED_SUFFIX", reclamation),
    ("_UNFOLLOWED", reclamation),
    ("_UNLINKED", reclamation),
    ("_VERIFY_QUIETLY", evidence),
    ("_VERIFY_REF", creation),
    ("_WORKTREE_ADD", creation),
    ("_WORKTREE_REMOVE_FORCE", creation),
    ("_WRITABLE", reclamation),
    ("_aims_here", reclamation),
    ("_all_taken", reclamation),
    ("_anchor_checkout", obligations),
    ("_anchor_let_go", reclamation),
    ("_anchor_pr_worktree", creation),
    ("_anchor_ref", obligations),
    ("_anchor_settled", reclamation),
    ("_anchor_taken", reclamation),
    ("_anchor_target", creation),
    ("_anchored_commit", obligations),
    ("_a_note_stands_at", obligations),
    ("_a_note_to_write", obligations),
    ("_anchored_removal", reclamation),
    ("_anchors_prefix", obligations),
    ("_artifact_reading", eligibility),
    ("_artifact_verdict", eligibility),
    ("_aside_dropped", reclamation),
    ("_aside_moved", reclamation),
    ("_aside_repaired", reclamation),
    ("_aside_settled", reclamation),
    ("_attributed_issues", attribution),
    ("_base_contains", evidence),
    ("_branch_attribution", attribution),
    ("_branch_commit_count", recovery),
    ("_branch_has_unpushed_commits", recovery),
    ("_branch_lock", reclamation),
    ("_branch_name", paths),
    ("_branch_reasons", eligibility),
    ("_branch_ref", reclamation),
    ("_branch_retentions", eligibility),
    ("_branch_tip", eligibility),
    ("_came_down", reclamation),
    ("_candidate_issue_branches", recovery),
    ("_carrying_pull_request", claims),
    ("_checkout_entries", probes),
    ("_checkout_gitdir", reclamation),
    ("_checkout_gone", reclamation),
    ("_checkout_handle", reclamation),
    ("_checkout_head", eligibility),
    ("_checkout_held", reclamation),
    ("_checkout_identity", evidence),
    ("_checkout_present", reclamation),
    ("_checkout_reason", eligibility),
    ("_checkout_retentions", eligibility),
    ("_checkout_tip", evidence),
    ("_checkout_tip_retentions", eligibility),
    ("_classified_candidates", eligibility),
    ("_classify_artifacts", eligibility),
    ("_clean_worktree", evidence),
    ("_cleanup_decompose_worktree", decomposition),
    ("_cleanup_question_worktree", terminal),
    ("_cleanup_terminal_branch", terminal),
    ("_cleared_and_empty", reclamation),
    ("_clone_read", evidence),
    ("_colliding_worktree_slugs", attribution),
    ("_commit_accounting", claims),
    ("_commit_count_from_stdout", recovery),
    ("_common_git_dir", evidence),
    ("_decompose_worktree_path", decomposition),
    ("_delete_local_issue_branch", cleanup),
    ("_direct_note", obligations),
    ("_discard_anchor", obligations),
    ("_discharge_obligation", obligations),
    ("_dropped_note", obligations),
    ("_ended_retentions", claims),
    ("_ensure_decompose_worktree", decomposition),
    ("_ensure_pr_worktree", creation),
    ("_ensure_worktree", creation),
    ("_every_note_listed", obligations),
    ("_everything_held", reclamation),
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
    ("_left_aside", reclamation),
    ("_left_behind", reclamation),
    ("_let_go", reclamation),
    ("_local_branch_tip", evidence),
    ("_lock_created", reclamation),
    ("_lock_dropped", reclamation),
    ("_lock_filed", reclamation),
    ("_lock_moved", reclamation),
    ("_lock_names", reclamation),
    ("_lock_put_back", reclamation),
    ("_lock_says", reclamation),
    ("_lock_scratch", reclamation),
    ("_lock_staged", reclamation),
    ("_lock_still", reclamation),
    ("_lock_told", reclamation),
    ("_locks_unchanged", reclamation),
    ("_loose_note_names", obligations),
    ("_local_issue_inventory", inventory),
    ("_local_orchestrator_branches", probes),
    ("_matching_owners", attribution),
    ("_merged", inventory),
    ("_mode_put_back", reclamation),
    ("_mode_taken_off", reclamation),
    ("_move_branch_onto", creation),
    ("_moved_aside", reclamation),
    ("_note_at", obligations),
    ("_note_value", obligations),
    ("_nothing_ignored", evidence),
    ("_nothing_left", reclamation),
    ("_object_kind", obligations),
    ("_obligation_ref", obligations),
    ("_one_directory", reclamation),
    ("_one_to_put_back", reclamation),
    ("_open_pull_request_retentions", claims),
    ("_out_of_reach", reclamation),
    ("_own_locks", reclamation),
    ("_own_way_down", obligations),
    ("_parsed_record", obligations),
    ("_parsed_records", obligations),
    ("_pr_branch_start_point", creation),
    ("_process_alive", reclamation),
    ("_proven_tips", eligibility),
    ("_published_tip", evidence),
    ("_put_back", reclamation),
    ("_read_notes", obligations),
    ("_read_orchestrator_refs", probes),
    ("_read_state", claims),
    ("_ready_to_go", reclamation),
    ("_reclaim_artifacts", reclamation),
    ("_reclaimed_checkout", reclamation),
    ("_record_attribution", attribution),
    ("_record_obligation", obligations),
    ("_recorded_anchors", obligations),
    ("_recorded_notes", obligations),
    ("_recorded_obligations", obligations),
    ("_recorded_pull_request", claims),
    ("_records_prefix", obligations),
    ("_registration_aimed", reclamation),
    ("_registration_checked", reclamation),
    ("_registration_dropped", reclamation),
    ("_registration_filed", reclamation),
    ("_registration_given_back", reclamation),
    ("_registration_held", reclamation),
    ("_registration_now", reclamation),
    ("_registration_opened", reclamation),
    ("_registration_read", reclamation),
    ("_registration_replaced", reclamation),
    ("_registration_settled", reclamation),
    ("_registration_staged", reclamation),
    ("_registration_still", reclamation),
    ("_registration_taken", reclamation),
    ("_registration_thawed", reclamation),
    ("_registration_told", reclamation),
    ("_registration_unchanged", reclamation),
    ("_remind", obligations),
    ("_removal_aside", reclamation),
    ("_removal_under_lock", reclamation),
    ("_removal_while_held", reclamation),
    ("_remove_issue_worktree", cleanup),
    ("_removed_checkout", reclamation),
    ("_renamed", reclamation),
    ("_repo_worktrees_root", paths),
    ("_reported", reclamation),
    ("_repository_key", obligations),
    ("_reservation_let_go", reclamation),
    ("_reservation_reclaimed", reclamation),
    ("_resolve_branch_name", paths),
    ("_resolved_commit", creation),
    ("_resolved_root", inventory),
    ("_resolved_tip", evidence),
    ("_root_inventory", inventory),
    ("_run_decompose_worktree_removal", decomposition),
    ("_run_issue_worktree_removal", cleanup),
    ("_run_local_branch_deletion", cleanup),
    ("_same_object", reclamation),
    ("_same_place", reclamation),
    ("_sanitize_branch_segment", paths),
    ("_sanitize_slug", paths),
    ("_shared_ref_store", obligations),
    ("_shared_repository", evidence),
    ("_somewhere_aside", reclamation),
    ("_spent_anchor_cleared", reclamation),
    ("_standing_anchor", reclamation),
    ("_stands_as", obligations),
    ("_slug_digest", paths),
    ("_slugs_by_worktrees_root", attribution),
    ("_spec_inventory", inventory),
    ("_specs_by_clone", inventory),
    ("_still_cleared", reclamation),
    ("_still_held", reclamation),
    ("_still_ours", reclamation),
    ("_store_held", obligations),
    ("_taken_away", reclamation),
    ("_taken_once", reclamation),
    ("_terminal_retentions", claims),
    ("_thawed", reclamation),
    ("_tip_retentions", eligibility),
    ("_untouched", reclamation),
    ("_workflow_members", claims),
    ("_worktree_issue_numbers", probes),
    ("_walked_entry", obligations),
    ("_walked_into", obligations),
    ("_worktree_path", paths),
    ("_writes_here", obligations),
    ("_written_note", obligations),
    ("_written_over", reclamation),
    ("_written_whole", reclamation),
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
