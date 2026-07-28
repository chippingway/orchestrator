# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Skill-enumeration domain owners.

Home of the two ways this orchestrator answers "which skills are in play".
``catalog`` enumerates what a configured target repo *offers* on its base ref
and appends one ``repo_skill_catalog`` analytics record per tick per spec;
``discovery`` enumerates what a single local Codex run was *loaded with*,
scanning the run's worktree and the global Codex root because codex's stream
carries no offered-skills or offered-tools frame to read one off. The skill
roots and the ``SKILL.md`` marker that both scans are defined by live on
``discovery``, the owner that reaches nothing outside the standard library, and
``catalog`` reads them back so a git pathspec and a filesystem scan cannot
disagree about what a skill definition is.

Callers import the owner they need, so this initializer binds nothing: an
importer of ``discovery`` pays for neither the analytics sink nor git.
Neither owner may reach the workflow engine, a stage, or an application
entrypoint -- a catalog is observation the tick drives, never state it
consults, and the dependency runs one way.
``orchestrator.skill_catalog`` stays the historical import site until the last
caller names an owner here.
"""
