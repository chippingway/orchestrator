# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""What each ecosystem's Dependabot entry has to declare to GitHub.

Three blocks carry behavior. The service labels stamped on every update PR let
a reviewer select the dependency queue by label rather than by reading titles:
the shared one the whole queue is filtered by, plus the one naming which
ecosystem moved. The cooldown windows hold a release for a stabilization
period before an update PR opens, and both ecosystems run the same policy, so
a window rewritten on one of them and not the other is a divergence rather
than a decision. The `uv` allow rules name GitPython, which reaches the
lockfile only through Streamlit: an `allow:` block replaces Dependabot's
default rule instead of adding to it, so losing either rule either stops
direct updates outright or sends the grouped security job back to skipping the
whole group with no allowed dependency matched.

Nothing in the tree reads this config -- GitHub does -- so a dropped label, a
window quietly rewritten on one ecosystem, or a deleted allow rule would
otherwise surface only on the next update PR, once it had already failed to
open.

The check is a text match for the block each entry must carry rather than a
read of what it happens to declare: what GitHub has to receive is exact, so
matching it exactly is both the whole assertion and the reason no YAML reader
is needed here to make it. Only the comments are dropped first, so a line of
reasoning added beside a rule is not a failure.

The operator pages that tell a maintainer which label selects the dependency
queue spell the same strings out a second time, and a rename here would leave
them describing a filter that matches nothing, so they are checked against the
config rather than against a reader's memory of it.
"""
from __future__ import annotations

import unittest
from collections.abc import Iterable
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEPENDABOT_CONFIG = _REPO_ROOT / ".github" / "dependabot.yml"
_ECOSYSTEM_KEY = "  - package-ecosystem: "
_ENCODING = "utf-8"

# The labels every ecosystem's entry must declare, in file order.
_EXPECTED_LABELS = (
    ("github-actions", ("workflow:dependencies", "workflow:github_actions")),
    ("uv", ("workflow:dependencies", "workflow:python:uv")),
)
_ECOSYSTEMS = tuple(ecosystem for ecosystem, _ in _EXPECTED_LABELS)
_SERVICE_LABELS = frozenset(
    label for _, labels in _EXPECTED_LABELS for label in labels
)
# The one cooldown policy both ecosystems run: a major, and anything SemVer
# does not classify, waits a month; a minor or a patch waits a fortnight.
_EXPECTED_COOLDOWN = (
    ("default-days", 30),
    ("semver-major-days", 30),
    ("semver-minor-days", 14),
    ("semver-patch-days", 14),
)
# The `uv` allow rules, in file order: the default rule the block would
# otherwise replace, then the transitive dependency the grouped security job
# needs named before GitPython's advisories reach it.
_EXPECTED_UV_ALLOW = (
    "dependency-type: direct",
    "dependency-name: gitpython",
)
_DOCUMENTING_PAGES = (
    Path("docs") / "configuration" / "operations.md",
    Path("docs") / "security.md",
)


def _block(key: str, declarations: Iterable[str]) -> str:
    """One `key:` block of an entry, as the entry has to spell it out."""
    lines = (f"      {declaration}" for declaration in declarations)
    return "\n".join((f"    {key}:", *lines))


def _entry_declarations(ecosystem: str) -> str:
    """One entry's lines, from its ecosystem key to where the next starts."""
    config = _DEPENDABOT_CONFIG.read_text(encoding=_ENCODING)
    below_key = config.partition(f"{_ECOSYSTEM_KEY}{ecosystem}\n")[2]
    return "\n".join(
        line
        for line in below_key.split(_ECOSYSTEM_KEY)[0].splitlines()
        if not line.lstrip().startswith("#")
    )


class DependabotServiceLabelsTest(unittest.TestCase):
    def test_ecosystems_declare_their_labels(self) -> None:
        for ecosystem, labels in _EXPECTED_LABELS:
            declared = _block(
                "labels", (f'- "{label}"' for label in labels),
            )
            with self.subTest(ecosystem=ecosystem):
                self.assertIn(declared, _entry_declarations(ecosystem))


class DependabotCooldownPolicyTest(unittest.TestCase):
    def test_ecosystems_share_one_cooldown_policy(self) -> None:
        declared = _block(
            "cooldown",
            (f"{window}: {days}" for window, days in _EXPECTED_COOLDOWN),
        )
        for ecosystem in _ECOSYSTEMS:
            with self.subTest(ecosystem=ecosystem):
                self.assertIn(declared, _entry_declarations(ecosystem))


class DependabotAllowRulesTest(unittest.TestCase):
    def test_uv_allows_direct_updates_and_gitpython(self) -> None:
        declared = _block(
            "allow", (f"- {rule}" for rule in _EXPECTED_UV_ALLOW),
        )
        self.assertIn(declared, _entry_declarations("uv"))


class DocumentedServiceLabelsTest(unittest.TestCase):
    def test_pages_name_every_service_label(self) -> None:
        for page in _DOCUMENTING_PAGES:
            prose = (_REPO_ROOT / page).read_text(encoding=_ENCODING)
            for label in sorted(_SERVICE_LABELS):
                with self.subTest(page=page.name, label=label):
                    self.assertIn(f"`{label}`", prose)


if __name__ == "__main__":
    unittest.main()
