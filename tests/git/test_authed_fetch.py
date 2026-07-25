# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""In-worktree authenticated fetch owned by the authentication module."""

from __future__ import annotations

import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from orchestrator import config
from orchestrator.git import authentication

from tests.git.authentication_test_support import (
    FAKE_TOKEN,
    REPOSITORY_SLUG,
    SUBPROCESS_RUN,
    TEMP_ROOT,
    TOKEN_RESOLVER,
    _assert_hardened_fetch,
    _spec,
)
from tests.workflow_git_helpers import (
    _GitRunRecorder,
    _TokenResolver,
    _temp_git_repo_with_local_config,
)

FORCED_MAIN_REFSPEC = "+refs/heads/main:refs/remotes/origin/main"
HTTP_PROXY_KEY = "http.proxy"


def _clean_probe() -> MagicMock:
    """Return a transport probe reporting no hijacking config."""
    return MagicMock(returncode=1, stdout="", stderr="")


class AuthedFetchHardeningTest(unittest.TestCase):
    """`_authed_fetch` is the in-worktree authenticated fetch helper used
    by `_handle_resolving_conflict`. Mirrors `_push_branch`'s security
    envelope: askpass-based auth, detached global/system config, blocked
    hooks/fsmonitor/credential helpers, refusal to run when the worktree
    carries url-rewrite rules or http.* proxy/TLS transport config.
    """

    def test_askpass_token_blocks_inherited_config(self) -> None:
        # First subprocess.run call is the rewrite-rule probe (returncode=1
        # = no rewrite rules); second is the real fetch -- capture its env.
        run_recorder = _GitRunRecorder(probe_result=_clean_probe())

        with (
            patch(SUBPROCESS_RUN, side_effect=run_recorder),
            patch.object(config, TOKEN_RESOLVER, return_value=FAKE_TOKEN),
        ):
            authentication._authed_fetch(
                _spec(),
                FORCED_MAIN_REFSPEC,
                cwd=TEMP_ROOT,
            )

        _assert_hardened_fetch(self, run_recorder, FAKE_TOKEN)

    def test_url_rewrite_rule_is_refused(self) -> None:
        # Rewrite-rule probe returns a hit; the real fetch must NOT run.
        run_recorder = _GitRunRecorder(
            probe_result=MagicMock(
                returncode=0,
                stdout=("url.https://evil.example/.insteadof https://github.com/\n"),
                stderr="",
            ),
        )

        with (
            patch(SUBPROCESS_RUN, side_effect=run_recorder),
            patch.object(config, TOKEN_RESOLVER, return_value=FAKE_TOKEN),
        ):
            fetch = authentication._authed_fetch(
                _spec(),
                FORCED_MAIN_REFSPEC,
                cwd=TEMP_ROOT,
            )

        # Only the rewrite probe ran -- the fetch was refused.
        self.assertEqual(len(run_recorder.calls), 1)
        self.assertNotEqual(fetch.returncode, 0)

    def test_refuses_on_real_local_http_proxy(self) -> None:
        # The url-rewrite refusal test above mocks the config probe, so it
        # can't prove the broadened regexp actually catches http.* keys. Use
        # real git config resolution: a worktree carrying `http.proxy` must
        # make `_authed_fetch` fail closed before the token-bearing fetch runs.
        log_capture = MagicMock()
        with ExitStack() as stack:
            repo = stack.enter_context(
                _temp_git_repo_with_local_config([(HTTP_PROXY_KEY, "http://evil.example:8080")]),
            )
            stack.enter_context(
                patch.object(config, TOKEN_RESOLVER, return_value=FAKE_TOKEN),
            )
            log_capture.records = stack.enter_context(
                self.assertLogs(authentication.log, level="ERROR"),
            )
            fetch = authentication._authed_fetch(
                _spec(),
                FORCED_MAIN_REFSPEC,
                cwd=repo,
            )
        self.assertNotEqual(fetch.returncode, 0)
        self.assertTrue(
            any(HTTP_PROXY_KEY in line for line in log_capture.records.output),
            "expected http.proxy in refusal log, got {!r}".format(log_capture.records.output),
        )

    def test_no_token_fails_without_subprocess(self) -> None:
        subprocess_run = MagicMock()

        with (
            patch(SUBPROCESS_RUN, subprocess_run),
            patch.object(config, TOKEN_RESOLVER, return_value=""),
        ):
            fetch = authentication._authed_fetch(
                _spec(),
                FORCED_MAIN_REFSPEC,
                cwd=TEMP_ROOT,
            )

        # No subprocess at all when the token is missing.
        subprocess_run.assert_not_called()
        self.assertNotEqual(fetch.returncode, 0)

    def test_uses_per_spec_token_for_git_fetch(self) -> None:
        # Multi-repo regression guard: `_authed_fetch` must resolve the token
        # from `spec.slug` (so a per-repo `~/.config/<owner>/<repo>/token`
        # file is honored), not from the cached single-repo
        # `config.GITHUB_TOKEN` looked up once for `config.REPO`. Without
        # this, `_handle_resolving_conflict` fetches origin/<branch> /
        # origin/<base> with the wrong (or empty) token for any repo other
        # than the legacy single-repo `REPO`.
        run_recorder = _GitRunRecorder(probe_result=_clean_probe())
        token_resolver = _TokenResolver()

        with (
            patch(SUBPROCESS_RUN, side_effect=run_recorder),
            patch.object(config, TOKEN_RESOLVER, token_resolver),
        ):
            fetch = authentication._authed_fetch(
                _spec(REPOSITORY_SLUG),
                FORCED_MAIN_REFSPEC,
                cwd=TEMP_ROOT,
            )
        self.assertEqual(fetch.returncode, 0)
        # Token resolved exactly once, for the spec's slug -- not for
        # `config.REPO`.
        self.assertEqual(token_resolver.slugs, [REPOSITORY_SLUG])
        self.assertEqual(
            run_recorder.env.get("GIT_TOKEN"),
            "ghp-token-for-acme-widgets",
        )
        # Auth URL targets the spec's slug, not the cached config.REPO.
        self.assertIn(
            "https://x-access-token@github.com/acme/widgets.git",
            run_recorder.args,
        )

    def test_missing_per_spec_token_logs_slug(self) -> None:
        # A multi-repo deployment that forgot to populate the per-slug token
        # file should fail the fetch with the misconfigured slug surfaced in
        # the error log -- the resolving_conflict handler then parks awaiting
        # human, which is far more debuggable than a generic "GITHUB_TOKEN
        # missing" with no repo identifier.
        subprocess_run = MagicMock()

        log_capture = MagicMock()
        with ExitStack() as stack:
            stack.enter_context(patch(SUBPROCESS_RUN, subprocess_run))
            stack.enter_context(
                patch.object(config, TOKEN_RESOLVER, return_value=""),
            )
            log_capture.records = stack.enter_context(
                self.assertLogs(authentication.log, level="ERROR"),
            )
            fetch = authentication._authed_fetch(
                _spec(REPOSITORY_SLUG),
                FORCED_MAIN_REFSPEC,
                cwd=TEMP_ROOT,
            )
        # Fetch aborted before any subprocess ran.
        subprocess_run.assert_not_called()
        self.assertNotEqual(fetch.returncode, 0)
        self.assertTrue(
            any(REPOSITORY_SLUG in line for line in log_capture.records.output),
            "expected slug 'acme/widgets' in log output, got {!r}".format(log_capture.records.output),
        )


if __name__ == "__main__":
    unittest.main()
