# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Filesystem discovery of skills and tools offered to local Codex runs.

Codex's `codex exec --json` stream -- unlike claude's `system`/`init` frame --
carries no offered-skills or offered-tools catalog, so a codex run's
`skills_available` / `tools` would stay empty. As an out-of-band workaround
`discover_local_skill_sources` scans, directly on the filesystem, the repo
skill roots under the run's worktree plus the global `$CODEX_HOME/skills` codex
loads -- including the built-in skills under that global root's `.system`
container -- and pairs every name it finds with the source level that defined
it: `project` for a worktree root, `user` for a direct global entry, `harness`
for a `.system` built-in. `discover_local_skills` is the names-only projection
of that scan. Both are fail-open (a missing root contributes nothing) and read
only skill *names*, never `SKILL.md` contents. `discover_codex_tools` returns a
best-effort static baseline of codex exec's offered tools (codex's stream,
unlike its skill files, exposes no filesystem source for these).

The roots and the marker file are defined here rather than beside the caller
that scans them hardest: this owner reaches nothing outside the standard
library, so `catalog` can read them back and the two enumerations cannot
disagree about what a skill definition is.
"""
from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from typing import NamedTuple

# Skill roots, in the order a repo definition takes precedence over a global
# one. Both are relative: `catalog` passes them to `git ls-tree` as pathspecs
# on a base ref, while the scans here join them onto a worktree.
_SKILL_ROOTS = (".agents/skills", ".claude/skills")

# The single file that marks a skill definition. Only a file with exactly this
# name, sitting directly under `<root>/<name>/`, defines a skill.
_SKILL_FILE = "SKILL.md"

_SYSTEM_SKILL_DIR = ".system"

# The three levels a definition can come from, ordered by what shadows what: a
# worktree root's `project` definition wins over an operator's `user` one under
# the global Codex root, which in turn wins over the `harness` built-in codex
# ships in that root's `.system` container. Spelled as plain strings because a
# consumer records them verbatim.
_PROJECT_LEVEL = "project"
_USER_LEVEL = "user"
_HARNESS_LEVEL = "harness"


class SkillSource(NamedTuple):
    """A discovered skill name and the source level that defined it."""

    name: str
    level: str


def _direct_skill_names(root: Path) -> list[str]:
    """Return direct ``<root>/<name>/SKILL.md`` skill names."""
    names: list[str] = []
    try:
        entries = list(os.scandir(root))
    except OSError:
        return names
    for entry in entries:
        if entry.name.startswith("."):
            continue
        with suppress(OSError):
            if entry.is_dir() and (Path(entry.path) / _SKILL_FILE).is_file():
                names.append(entry.name)
    return sorted(names)


def _skill_sources(root: Path, level: str) -> list[SkillSource]:
    """Pair every direct skill name under ``root`` with ``level``."""
    return [
        SkillSource(skill_name, level)
        for skill_name in _direct_skill_names(root)
    ]


def _global_codex_skill_sources() -> list[SkillSource]:
    """Collect user and built-in skill sources from the global Codex root.

    The two global levels are merged into a single name-sorted run so they
    order as one directory would, and a name the operator installed directly
    under the root shadows the built-in of the same name.
    """
    codex_home = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    global_root = Path(codex_home) / "skills"
    global_sources = (
        _skill_sources(global_root / _SYSTEM_SKILL_DIR, _HARNESS_LEVEL)
        + _skill_sources(global_root, _USER_LEVEL)
    )
    by_name = {
        skill_source.name: skill_source
        for skill_source in global_sources
    }
    return [by_name[skill_name] for skill_name in sorted(by_name)]


def discover_local_skill_sources(cwd: Path) -> tuple[SkillSource, ...]:
    """Enumerate name/level pairs available to a Codex run rooted at ``cwd``.

    Repository roots are ordered before the global Codex roots and missing or
    unreadable directories contribute nothing. A duplicate name is reported
    once, carrying the level of the definition that shadows the others. Only
    names and levels are read; skill instruction contents remain outside
    analytics collection.
    """
    project_sources = [
        project_source
        for skill_root in _SKILL_ROOTS
        for project_source in _skill_sources(cwd / skill_root, _PROJECT_LEVEL)
    ]
    seen_sources: dict[str, SkillSource] = {}
    for skill_source in (*project_sources, *_global_codex_skill_sources()):
        seen_sources.setdefault(skill_source.name, skill_source)
    return tuple(seen_sources.values())


def discover_local_skills(cwd: Path) -> tuple[str, ...]:
    """Enumerate names available to a Codex run rooted at ``cwd``.

    The names-only projection of `discover_local_skill_sources`, in that scan's
    order, for the consumers that record availability without provenance.
    """
    return tuple(
        skill_source.name
        for skill_source in discover_local_skill_sources(cwd)
    )


_CODEX_OFFERED_TOOLS: tuple[str, ...] = (
    "exec_command",
    "write_stdin",
    "update_plan",
    "request_user_input",
    "view_image",
    "multi_agent_v1",
    "get_goal",
    "create_goal",
    "update_goal",
    "web_search",
)


def discover_codex_tools() -> tuple[str, ...]:
    """Return the best-effort Codex offered-tools baseline."""
    return _CODEX_OFFERED_TOOLS
