# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Local skill and Codex tool discovery tests."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.skills import discovery

from tests.skills.skills_test_support import _make_skill


_DEVELOP_SKILL = "develop"
_REVIEW_SKILL = "review"
_IMAGEGEN_SKILL = "imagegen"
_AGENT_SKILLS_ROOT = ".agents/skills"
_CLAUDE_SKILLS_ROOT = ".claude/skills"
_SKILLS_DIR = "skills"
_SYSTEM_DIR = ".system"
_CODEX_HOME_ENV = "CODEX_HOME"

# The level vocabulary a consumer records verbatim, spelled out here so a
# change to one of the values has to be a change to this table too.
_PROJECT = "project"
_USER = "user"
_HARNESS = "harness"

_EXTRA_SKILL = "extra"
_GLOBAL_SKILL = "global-skill"
_WORKTREE_DIR = "wt"
_CODEX_HOME_DIR = "codexhome"

# Sorts after every other global name, so an ordering that grouped the two
# global levels instead of merging them would move it.
_LAST_USER_SKILL = "zzz-user-skill"


def _make_project_skill(
    cwd: Path,
    name: str,
    root: str = _AGENT_SKILLS_ROOT,
) -> None:
    """Define a skill under one of the worktree's repo roots."""
    _make_skill(cwd / root, name)


def _make_user_skill(home: Path, name: str) -> None:
    """Define a skill directly under the global Codex root."""
    _make_skill(home / _SKILLS_DIR, name)


def _make_harness_skill(home: Path, name: str) -> None:
    """Define a built-in under the global root's `.system` container."""
    _make_skill(home / _SKILLS_DIR / _SYSTEM_DIR, name)


def _discovered_names(cwd: Path) -> tuple[str, ...]:
    """The names one scan reports, for the cases no level varies across."""
    return tuple(
        skill_source.name
        for skill_source in discovery.discover_local_skill_sources(cwd)
    )


class SkillScanMembershipTest(unittest.TestCase):
    """Which definitions one scan reports, and in which order."""

    def test_scans_both_repo_roots_and_dedups(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            cwd = Path(repo_dir)
            _make_project_skill(cwd, _DEVELOP_SKILL)
            _make_project_skill(cwd, _REVIEW_SKILL)
            _make_project_skill(cwd, _DEVELOP_SKILL, _CLAUDE_SKILLS_ROOT)
            _make_project_skill(cwd, _EXTRA_SKILL, _CLAUDE_SKILLS_ROOT)
            with patch.dict(
                os.environ,
                {_CODEX_HOME_ENV: str(cwd / "no-home")},
            ):
                names = _discovered_names(cwd)
        self.assertEqual(
            names,
            (_DEVELOP_SKILL, _REVIEW_SKILL, _EXTRA_SKILL),
        )

    def test_includes_codex_home_global_skills(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            cwd = Path(home_dir) / _WORKTREE_DIR
            home = Path(home_dir) / _CODEX_HOME_DIR
            _make_project_skill(cwd, _REVIEW_SKILL)
            _make_user_skill(home, _GLOBAL_SKILL)
            _make_harness_skill(home, _IMAGEGEN_SKILL)
            with patch.dict(os.environ, {_CODEX_HOME_ENV: str(home)}):
                names = _discovered_names(cwd)
        self.assertEqual(
            names,
            (_REVIEW_SKILL, _GLOBAL_SKILL, _IMAGEGEN_SKILL),
        )

    def test_global_system_builtins_surface_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as system_dir:
            cwd = Path(system_dir) / _WORKTREE_DIR
            home = Path(system_dir) / _CODEX_HOME_DIR
            for name in (
                _IMAGEGEN_SKILL,
                "openai-docs",
                "skill-installer",
            ):
                _make_harness_skill(home, name)
            with patch.dict(os.environ, {_CODEX_HOME_ENV: str(home)}):
                names = _discovered_names(cwd)
        self.assertEqual(
            names,
            (_IMAGEGEN_SKILL, "openai-docs", "skill-installer"),
        )

    def test_repo_skill_precedes_global_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as duplicate_dir:
            cwd = Path(duplicate_dir) / _WORKTREE_DIR
            home = Path(duplicate_dir) / _CODEX_HOME_DIR
            _make_project_skill(cwd, _REVIEW_SKILL)
            _make_user_skill(home, _REVIEW_SKILL)
            with patch.dict(os.environ, {_CODEX_HOME_ENV: str(home)}):
                names = _discovered_names(cwd)
        self.assertEqual(names, (_REVIEW_SKILL,))

    def test_only_direct_children_with_skill_md_count(self) -> None:
        with tempfile.TemporaryDirectory() as direct_dir:
            cwd = Path(direct_dir)
            root = cwd / _AGENT_SKILLS_ROOT
            _make_skill(root, _DEVELOP_SKILL)
            (root / "empty").mkdir(parents=True, exist_ok=True)
            deep = root / _SYSTEM_DIR / _IMAGEGEN_SKILL
            deep.mkdir(parents=True, exist_ok=True)
            (deep / "SKILL.md").write_text("x", encoding="utf-8")
            with patch.dict(
                os.environ,
                {_CODEX_HOME_ENV: str(cwd / "no-home")},
            ):
                names = _discovered_names(cwd)
        self.assertEqual(names, (_DEVELOP_SKILL,))

    def test_missing_roots_yield_empty_not_error(self) -> None:
        with tempfile.TemporaryDirectory() as missing_dir:
            cwd = Path(missing_dir) / "does-not-exist"
            missing_home = {
                _CODEX_HOME_ENV: str(Path(missing_dir) / "nope"),
            }
            with patch.dict(os.environ, missing_home):
                self.assertEqual(
                    discovery.discover_local_skill_sources(cwd),
                    (),
                )


class SkillScanProvenanceTest(unittest.TestCase):
    """Every discovered name carries the level of the root that defined it."""

    def test_each_root_stamps_its_own_level(self) -> None:
        with tempfile.TemporaryDirectory() as level_dir:
            cwd = Path(level_dir) / _WORKTREE_DIR
            home = Path(level_dir) / _CODEX_HOME_DIR
            _make_project_skill(cwd, _DEVELOP_SKILL)
            _make_project_skill(cwd, _EXTRA_SKILL, _CLAUDE_SKILLS_ROOT)
            _make_user_skill(home, _GLOBAL_SKILL)
            _make_harness_skill(home, _IMAGEGEN_SKILL)
            with patch.dict(os.environ, {_CODEX_HOME_ENV: str(home)}):
                sources = discovery.discover_local_skill_sources(cwd)
        self.assertEqual(
            sources,
            (
                discovery.SkillSource(_DEVELOP_SKILL, _PROJECT),
                discovery.SkillSource(_EXTRA_SKILL, _PROJECT),
                discovery.SkillSource(_GLOBAL_SKILL, _USER),
                discovery.SkillSource(_IMAGEGEN_SKILL, _HARNESS),
            ),
        )

    def test_shadowed_name_takes_the_winning_level(self) -> None:
        # A worktree definition outranks both global levels, and an operator's
        # own global skill outranks the built-in it replaces -- so which
        # directory a duplicate is attributed to never depends on scan order.
        with tempfile.TemporaryDirectory() as shadow_dir:
            cwd = Path(shadow_dir) / _WORKTREE_DIR
            home = Path(shadow_dir) / _CODEX_HOME_DIR
            _make_project_skill(cwd, _REVIEW_SKILL)
            for shadowed in (_REVIEW_SKILL, _IMAGEGEN_SKILL):
                _make_user_skill(home, shadowed)
                _make_harness_skill(home, shadowed)
            with patch.dict(os.environ, {_CODEX_HOME_ENV: str(home)}):
                sources = discovery.discover_local_skill_sources(cwd)
        self.assertEqual(
            sources,
            (
                discovery.SkillSource(_REVIEW_SKILL, _PROJECT),
                discovery.SkillSource(_IMAGEGEN_SKILL, _USER),
            ),
        )

    def test_global_levels_order_as_one_directory(self) -> None:
        # The two global levels merge into a single name-sorted run, so a user
        # skill whose name sorts last stays last instead of being grouped
        # ahead of the built-ins.
        with tempfile.TemporaryDirectory() as project_dir:
            cwd = Path(project_dir) / _WORKTREE_DIR
            home = Path(project_dir) / _CODEX_HOME_DIR
            _make_project_skill(cwd, _REVIEW_SKILL)
            _make_user_skill(home, _LAST_USER_SKILL)
            _make_harness_skill(home, _IMAGEGEN_SKILL)
            with patch.dict(os.environ, {_CODEX_HOME_ENV: str(home)}):
                sources = discovery.discover_local_skill_sources(cwd)
        self.assertEqual(
            tuple(skill_source.name for skill_source in sources),
            (_REVIEW_SKILL, _IMAGEGEN_SKILL, _LAST_USER_SKILL),
        )


class DiscoverCodexToolsTest(unittest.TestCase):
    def test_returns_nonempty_baseline(self) -> None:
        tools = discovery.discover_codex_tools()
        self.assertIsInstance(tools, tuple)
        self.assertEqual(tools, discovery._CODEX_OFFERED_TOOLS)
        self.assertIn("exec_command", tools)
        self.assertIn("web_search", tools)
        self.assertTrue(all(
            isinstance(tool, str)
            for tool in tools
        ))
        self.assertTrue(all(tools))
        self.assertEqual(len(tools), len(set(tools)))
