# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Real-git transport configuration guards for authenticated publication."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import git_plumbing, workflow

from tests.workflow_helpers import (
    _TEST_SPEC,
    _temp_git_repo_with_local_config,
)

ISSUE_BRANCH = "orchestrator/issue-5"
TOKEN_RESOLVER_ATTR = "_resolve_github_token"
HTTP_PROXY_KEY = "http.proxy"


class TransportConfigHardeningTest(unittest.TestCase):
    """Authenticated git operations reject agent-writable transport config."""

    def test_push_refused_on_real_local_http_proxy(self) -> None:
        with (
            _temp_git_repo_with_local_config([(HTTP_PROXY_KEY, "http://evil.example:8080")]) as repo,
            patch.object(
                workflow.config,
                TOKEN_RESOLVER_ATTR,
                return_value="ghp-test-secret",
            ),
            self.assertLogs(git_plumbing.log, level="ERROR") as logs,
        ):
            ok = workflow._push_branch(_TEST_SPEC, repo, ISSUE_BRANCH)
            log_output = logs.output
        self.assertFalse(ok)
        self.assertTrue(
            any(HTTP_PROXY_KEY in line for line in log_output),
            f"expected {HTTP_PROXY_KEY} in refusal log, got {log_output!r}",
        )
