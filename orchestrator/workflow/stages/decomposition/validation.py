# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What a `split` payload must satisfy before any child issue is created.

Every rule here is checked against a decomposer reply that has already decoded
as JSON, and every one of them is the last chance to reject it: past this point
`_create_child_issues` starts opening real GitHub issues, and a manifest that
turns out to be malformed halfway through leaves orphans behind that only an
operator can clean up. So the bound on the child count, the shape of each
child, and the acyclicity of the graph they declare are all decided together
and before anything is written.

`_MAX_CHILDREN` is the bound the decompose prompt states verbatim, and
`orchestrator.workflow.engine.prompts` reads it back from here so the number
the agent is told and the number it is judged against cannot drift apart.
"""
from __future__ import annotations

from typing import Optional, Tuple

_MAX_CHILDREN = 10


def _split_manifest_children(
    manifest: dict,
) -> Tuple[Optional[list], Optional[str]]:
    """Return the bounded, non-empty children list for a split decision."""
    children = manifest.get("children")
    if not isinstance(children, list) or not children:
        return None, "split decision requires non-empty children list"
    if len(children) > _MAX_CHILDREN:
        return None, f"too many children ({len(children)} > {_MAX_CHILDREN})"
    return children, None


def _manifest_umbrella_error(manifest: dict) -> Optional[str]:
    """Validate the optional umbrella flag without truthy coercion."""
    umbrella = manifest.get("umbrella")
    if umbrella is not None and not isinstance(umbrella, bool):
        return "umbrella must be a boolean"
    return None


def _is_nonempty_text(text_value: object) -> bool:
    return isinstance(text_value, str) and bool(text_value)


def _manifest_child_text_error(
    child: object, child_index: int,
) -> Optional[str]:
    """Validate one child object and its required text fields."""
    if not isinstance(child, dict):
        return f"child {child_index} is not an object"
    if not _is_nonempty_text(child.get("title")):
        return f"child {child_index} missing title or body"
    if not _is_nonempty_text(child.get("body")):
        return f"child {child_index} missing title or body"
    return None


def _manifest_child_dependencies(
    child: dict, child_index: int,
) -> Tuple[Optional[list], Optional[str]]:
    """Normalize null dependencies and reject every other non-list shape."""
    dependencies = child.get("depends_on")
    if dependencies is None:
        return [], None
    if not isinstance(dependencies, list):
        return None, f"child {child_index} depends_on must be a list"
    return dependencies, None


def _is_valid_dependency(
    dependency_index: object,
    *,
    child_index: int,
    child_count: int,
) -> bool:
    """Validate type, bounds, and the no-self-edge invariant."""
    if isinstance(dependency_index, bool):
        return False
    if not isinstance(dependency_index, int):
        return False
    if dependency_index < 0 or dependency_index >= child_count:
        return False
    return dependency_index != child_index


def _manifest_child_error(
    child: object, child_index: int, child_count: int,
) -> Optional[str]:
    """Return the first structural error for one split child."""
    text_error = _manifest_child_text_error(child, child_index)
    if text_error is not None:
        return text_error
    dependencies, dependency_error = _manifest_child_dependencies(
        child, child_index,
    )
    if dependency_error is not None:
        return dependency_error
    for dependency_index in dependencies or []:
        if not _is_valid_dependency(
            dependency_index,
            child_index=child_index,
            child_count=child_count,
        ):
            return (
                f"child {child_index} has invalid dependency "
                f"{dependency_index!r}"
            )
    return None


def _dep_cycle_visit(
    child_index: int, children: list[dict], color: list[int],
) -> bool:
    """DFS one node of the children dep graph; True on a back-edge to a node
    still on the stack.

    `color` is mutated in place (0=unvisited, 1=on-stack, 2=finished) and
    shared across the whole walk, so a node finished on one root is never
    re-descended from another.
    """
    color[child_index] = 1
    for dependency_index in (children[child_index].get("depends_on") or []):
        if color[dependency_index] == 1:
            return True
        if color[dependency_index] == 0 and _dep_cycle_visit(
            dependency_index, children, color,
        ):
            return True
    color[child_index] = 2
    return False


def _has_dep_cycle(children: list[dict]) -> bool:
    """DFS for back-edges in the children dep graph (white/gray/black)."""
    color = [0 for _ in children]  # 0=unvisited, 1=on-stack, 2=finished
    return any(
        color[child_index] == 0
        and _dep_cycle_visit(child_index, children, color)
        for child_index in range(len(children))
    )


def _manifest_children_error(children: list) -> Optional[str]:
    """Validate every child and then the dependency graph as a whole."""
    for child_index, child in enumerate(children):
        child_error = _manifest_child_error(
            child, child_index, len(children),
        )
        if child_error is not None:
            return child_error
    if _has_dep_cycle(children):
        return "dependency graph has a cycle"
    return None


def _split_manifest_error(manifest: dict) -> Optional[str]:
    """Return the first split-only manifest validation error."""
    children, children_error = _split_manifest_children(manifest)
    if children_error is not None:
        return children_error
    umbrella_error = _manifest_umbrella_error(manifest)
    if umbrella_error is not None:
        return umbrella_error
    return _manifest_children_error(children or [])
