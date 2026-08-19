# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Every in-repo Markdown anchor link resolves to a heading that exists.

A cross-document link is the one reference nothing else checks: renaming a
heading leaves the link syntactically valid and silently pointing nowhere, and
the reader who follows it lands at the top of the page instead. The headings
here embed values that do change -- a handler's label is in its heading -- so
the check is what turns the next such rename into a test failure rather than a
dead link somebody has to notice by hand.
"""
from __future__ import annotations

import posixpath
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MARKDOWN_LINK = re.compile(r"\]\(([^)\s]*?)#([^)\s]+)\)")
_MARKDOWN_REFERENCE = re.compile(r"^\[[^\]]+\]:\s*(\S*?)#(\S+)\s*$", re.M)
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.M)
_PUNCTUATION = re.compile(r"[^\w\s-]")
_ENCODING = "utf-8"


def _heading_anchor(heading: str) -> str:
    """Slug a heading the way GitHub does: drop punctuation, space -> hyphen.

    Punctuation is removed in place rather than replaced, so the `:` in a
    namespaced label closes up while the spaces around an em dash each still
    become their own hyphen.
    """
    return _PUNCTUATION.sub("", heading.strip().lower()).replace(" ", "-")


def _tracked_markdown() -> dict[str, Path]:
    """Every tracked page, keyed by the repo-relative path a link names it by.

    `docs/` nests, so the key has to carry the directory: two pages named
    `observability.md` sit one level apart, and a bare filename would resolve
    a link into whichever of them the dictionary happened to keep.
    """
    docs = {
        path.relative_to(_REPO_ROOT).as_posix(): path
        for path in (_REPO_ROOT / "docs").rglob("*.md")
    }
    docs["README.md"] = _REPO_ROOT / "README.md"
    return docs


def _anchors_by_document(docs: dict[str, Path]) -> dict[str, set[str]]:
    return {
        name: {
            _heading_anchor(heading)
            for heading in _MARKDOWN_HEADING.findall(
                path.read_text(encoding=_ENCODING),
            )
        }
        for name, path in docs.items()
    }


def _anchor_links(name: str, path: Path) -> list[tuple[str, str]]:
    """Every `(target document, anchor)` one document links to.

    A relative target is resolved against the directory of the page that wrote
    it, so the `../` a nested page reaches a sibling directory with names the
    same key the flat page beside it writes directly. A same-page `#anchor`
    link carries no target at all and stays on its own page. Both link forms
    count, since a reference definition at the foot of a page is how the
    longest anchors here are written.
    """
    directory = posixpath.dirname(name)
    text = path.read_text(encoding=_ENCODING)
    return [
        (
            posixpath.normpath(posixpath.join(directory, target))
            if target
            else name,
            anchor,
        )
        for target, anchor in (
            *_MARKDOWN_LINK.findall(text),
            *_MARKDOWN_REFERENCE.findall(text),
        )
    ]


def _dangling_links(docs: dict[str, Path]) -> list[str]:
    """Report every `...#anchor` link whose target heading is missing.

    Links out to another repository are skipped: only a document this repo
    tracks has headings this check can resolve the anchor against.
    """
    anchors = _anchors_by_document(docs)
    return [
        f"{name} -> {target}#{anchor}"
        for name, path in docs.items()
        for target, anchor in _anchor_links(name, path)
        if target in anchors and anchor not in anchors[target]
    ]


class DocumentAnchorTest(unittest.TestCase):
    """The scan reaches every tracked page, and no link in one dangles."""

    def test_every_anchor_link_resolves(self) -> None:
        self.assertEqual(_dangling_links(_tracked_markdown()), [])

    def test_discovery_reaches_documents_below_docs(self) -> None:
        """A guide split into a subdirectory is scanned, not skipped.

        A top-level-only scan leaves the nested pages passing by absence,
        which reads exactly like coverage until a link there rots.
        """
        nested = [name for name in _tracked_markdown() if name.count("/") > 1]
        self.assertTrue(nested, "no document below docs/ was discovered")

    def test_reference_definitions_are_scanned(self) -> None:
        """A foot-of-page definition is a link, and resolves like one."""
        with TemporaryDirectory() as directory:
            page = Path(directory) / "page.md"
            page.write_text(
                "[up](../landing.md#top)\n\n[ref]: ../landing.md#other\n",
                encoding=_ENCODING,
            )
            self.assertEqual(
                _anchor_links("docs/area/page.md", page),
                [("docs/landing.md", "top"), ("docs/landing.md", "other")],
            )


class HeadingAnchorSlugTest(unittest.TestCase):
    """The slug matches GitHub's, including the two cases that bite here."""

    def test_slug_matches_github(self) -> None:
        cases = (
            ("`_handle_validating` (label `workflow:validating`)",
             "_handle_validating-label-workflowvalidating"),
            ("In-flight session lock — pinned spec",
             "in-flight-session-lock--pinned-spec"),
        )
        for heading, expected in cases:
            with self.subTest(heading=heading):
                self.assertEqual(_heading_anchor(heading), expected)


if __name__ == "__main__":
    unittest.main()
