# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Every in-repo documentation link resolves, and the index reaches every page.

A cross-document link is the one reference nothing else checks: moving a page
or renaming a heading leaves the link syntactically valid and silently pointing
nowhere, and the reader who follows it gets a 404 or the top of the wrong page.
The headings here embed values that do change -- a handler's label is in its
heading -- and the hierarchy the index maps is split further as an area grows,
so these checks are what turn the next such move into a test failure rather
than a dead link somebody has to notice by hand.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.repository.doc_link_test_support import (
    ENTRY_POINTS,
    INDEX_PAGE,
    dangling_anchors,
    document_links,
    heading_anchor,
    tracked_markdown,
    unindexed_pages,
    unresolved_targets,
)

_ENCODING = "utf-8"
# One written link per case, with the paths the check is expected to report.
_PATH_CASES = (
    ("moved page", "[gone](docs/nowhere.md)", ("docs/nowhere.md",)),
    ("anchor on a moved page", "[x](docs/nowhere.md#top)", ("docs/nowhere.md",)),
    ("external link", "[ci](https://example.com/nowhere.md)", ()),
    ("same-page anchor", "[here](#top)", ()),
    ("page that exists", "[docs](docs/README.md)", ()),
)


class DocumentAnchorTest(unittest.TestCase):
    """The scan reaches every routed page, and no anchor in one dangles."""

    def test_every_anchor_link_resolves(self) -> None:
        self.assertEqual(dangling_anchors(tracked_markdown()), [])

    def test_discovery_reaches_documents_below_docs(self) -> None:
        """A guide split into a subdirectory is scanned, not skipped.

        A top-level-only scan leaves the nested pages passing by absence,
        which reads exactly like coverage until a link there rots.
        """
        nested = [name for name in tracked_markdown() if name.count("/") > 1]
        self.assertTrue(nested, "no document below docs/ was discovered")

    def test_discovery_reaches_the_routing_pages(self) -> None:
        """The agent entry point and the skills route, so they are scanned."""
        pages = tracked_markdown()
        for name in (*ENTRY_POINTS, ".agents/skills/develop/SKILL.md"):
            with self.subTest(page=name):
                self.assertIn(name, pages)

    def test_reference_definitions_are_scanned(self) -> None:
        """A foot-of-page definition is a link, and resolves like one."""
        with TemporaryDirectory() as directory:
            page = Path(directory) / "page.md"
            page.write_text(
                "[up](../landing.md#top)\n\n[ref]: ../landing.md#other\n",
                encoding=_ENCODING,
            )
            self.assertEqual(
                document_links("docs/area/page.md", page),
                [("docs/landing.md", "top"), ("docs/landing.md", "other")],
            )


class DocumentPathTest(unittest.TestCase):
    """No link names a file or directory the repository does not have."""

    def test_every_relative_link_resolves(self) -> None:
        self.assertEqual(unresolved_targets(tracked_markdown()), [])

    def test_only_a_missing_in_repo_path_is_reported(self) -> None:
        with TemporaryDirectory() as directory:
            page = Path(directory) / "page.md"
            for name, text, expected in _PATH_CASES:
                with self.subTest(case=name):
                    page.write_text(text, encoding=_ENCODING)
                    self.assertEqual(
                        unresolved_targets({"page.md": page}),
                        [f"page.md -> {target}" for target in expected],
                    )


class DocumentationIndexTest(unittest.TestCase):
    """The landing page is a map of the whole set, and both roads lead to it."""

    def test_the_index_links_every_page_under_docs(self) -> None:
        self.assertEqual(unindexed_pages(tracked_markdown()), [])

    def test_the_entry_points_route_to_the_index(self) -> None:
        pages = tracked_markdown()
        for name in ENTRY_POINTS:
            with self.subTest(page=name):
                linked = {
                    document
                    for document, _ in document_links(name, pages[name])
                }
                self.assertIn(INDEX_PAGE, linked)


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
                self.assertEqual(heading_anchor(heading), expected)


if __name__ == "__main__":
    unittest.main()
