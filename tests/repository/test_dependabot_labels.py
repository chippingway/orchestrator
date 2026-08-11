# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The service labels Dependabot stamps on the update PRs it opens.

Each ecosystem's PRs carry the shared label the whole dependency queue is
filtered by plus the one naming which ecosystem moved, so a reviewer selects
the queue by label rather than by reading titles.

Nothing in the tree reads this config -- GitHub does -- so a dropped label, or
one moved to the wrong ecosystem, would otherwise surface only on the next
update PR, once the labels were already wrong.

The check is a text match for the block each entry must carry rather than a
read of what it happens to declare: what GitHub has to receive is exact, so
matching it exactly is both the whole assertion and the reason no YAML reader
is needed here to make it.

The operator pages that tell a maintainer which label selects the dependency
queue spell the same strings out a second time, and a rename here would leave
them describing a filter that matches nothing, so they are checked against the
config rather than against a reader's memory of it.
"""
from __future__ import annotations

import unittest
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
_SERVICE_LABELS = frozenset(
    label for _, labels in _EXPECTED_LABELS for label in labels
)
_DOCUMENTING_PAGES = (
    Path("docs") / "configuration.md",
    Path("docs") / "security.md",
)


def _labels_block(labels: tuple[str, ...]) -> str:
    """The `labels:` sequence an entry declares those labels with."""
    lines = (f'      - "{label}"' for label in labels)
    return "\n".join(("    labels:", *lines))


def _entry_text(config: str, ecosystem: str) -> str:
    """One entry: from its ecosystem key down to where the next one starts."""
    below_key = config.partition(f"{_ECOSYSTEM_KEY}{ecosystem}\n")[2]
    return below_key.split(_ECOSYSTEM_KEY)[0]


class DependabotServiceLabelsTest(unittest.TestCase):
    def test_ecosystems_declare_their_labels(self) -> None:
        config = _DEPENDABOT_CONFIG.read_text(encoding=_ENCODING)
        for ecosystem, labels in _EXPECTED_LABELS:
            with self.subTest(ecosystem=ecosystem):
                self.assertIn(
                    _labels_block(labels), _entry_text(config, ecosystem),
                )


class DocumentedServiceLabelsTest(unittest.TestCase):
    def test_pages_name_every_service_label(self) -> None:
        for page in _DOCUMENTING_PAGES:
            prose = (_REPO_ROOT / page).read_text(encoding=_ENCODING)
            for label in sorted(_SERVICE_LABELS):
                with self.subTest(page=page.name, label=label):
                    self.assertIn(f"`{label}`", prose)


if __name__ == "__main__":
    unittest.main()
