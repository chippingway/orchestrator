# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Filesystem discovery of skills and tools offered to local Codex runs.

Codex's `codex exec --json` stream -- unlike claude's `system`/`init` frame --
carries no offered-skills or offered-tools catalog, so a codex run's
`skills_available` / `tools` would stay empty. As an out-of-band workaround
`discover_local_skills` scans, directly on the filesystem, the repo skill roots
under the run's worktree plus the global `$CODEX_HOME/skills` codex loads --
including the built-in skills under that global root's `.system` container. It
is fail-open (a missing root contributes nothing) and reads only skill *names*,
never `SKILL.md` contents. `discover_codex_tools` returns a best-effort static
baseline of codex exec's offered tools (codex's stream, unlike its skill files,
exposes no filesystem source for these).

The roots and the marker file are defined here rather than beside the caller
that scans them hardest: this owner reaches nothing outside the standard
library, so `catalog` can read them back and the two enumerations cannot
disagree about what a skill definition is.
"""
from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from typing import Iterable

# Skill roots, in the order a repo definition takes precedence over a global
# one. Both are relative: `catalog` passes them to `git ls-tree` as pathspecs
# on a base ref, while the scans here join them onto a worktree.
_SKILL_ROOTS = (".agents/skills", ".claude/skills")

# The single file that marks a skill definition. Only a file with exactly this
# name, sitting directly under `<root>/<name>/`, defines a skill.
_SKILL_FILE = "SKILL.md"

_SYSTEM_SKILL_DIR = ".system"


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


def _add_skill_names(
    seen_names: dict[str, None],
    skill_names: Iterable[str],
) -> None:
    """Add names to an insertion-ordered deduplication map."""
    for skill_name in skill_names:
        seen_names.setdefault(skill_name, None)


def _global_codex_skill_names() -> list[str]:
    """Collect user and built-in skill names from the global Codex root."""
    codex_home = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    global_root = Path(codex_home) / "skills"
    return sorted(set(
        _direct_skill_names(global_root)
        + _direct_skill_names(global_root / _SYSTEM_SKILL_DIR)
    ))


def discover_local_skills(cwd: Path) -> tuple[str, ...]:
    """Enumerate names available to a Codex run rooted at ``cwd``.

    Repository roots are ordered before the global Codex roots and missing or
    unreadable directories contribute nothing. Only names are read; skill
    instruction contents remain outside analytics collection.
    """
    seen_names: dict[str, None] = {}
    for skill_root in _SKILL_ROOTS:
        _add_skill_names(
            seen_names,
            _direct_skill_names(cwd / skill_root),
        )
    _add_skill_names(seen_names, _global_codex_skill_names())
    return tuple(seen_names)


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
