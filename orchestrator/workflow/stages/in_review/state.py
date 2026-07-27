# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The wire key the in_review owners scan and ratchet on.

`pr_last_comment_id` is the issue-side watermark, and it covers two surfaces
at once: the issue thread and the PR conversation share the IssueComment id
namespace, so one value decides what counts as fresh on both. It is written
into the pinned JSON comment live issues already carry -- the validating
handoff seeds it, the legacy migration backfills it, the fixing handler reads
it back -- so renaming it is a migration of every open PR rather than a
refactor.

It sits here rather than on the owner that ratchets it because the owner that
writes it is rarely the one that reads it: the handoff seeds, `watermarks`
ratchets, and `feedback` scans from it.
"""
from __future__ import annotations

_PR_LAST_COMMENT_ID = "pr_last_comment_id"
