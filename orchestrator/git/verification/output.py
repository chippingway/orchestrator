# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The redact-then-truncate pass every captured verify output goes through.

Both classification paths -- the timeout drain's partial bytes and a completed
command's merged stdout/stderr -- reach `VerifyResult.output` through this
owner, so the ordering the park comment depends on is stated once. It sits
below the process and runner owners and reaches the credentials owner directly
because redaction is a settings-layer concern, not a subprocess one.
"""
from __future__ import annotations

from orchestrator.config import credentials as _credentials
from orchestrator.git.verification import models as _models


def _truncate_verify_output(text: str) -> str:
    """Redact secrets, then keep the tail within `_VERIFY_OUTPUT_BUDGET`.

    Redaction MUST happen before the truncation. `redact_secrets` does a
    full-string `str.replace(value, "***")` against each candidate env
    value; if the truncation cut sliced a secret in half first, the
    surviving partial would no longer match the replace and would leak
    verbatim in the park comment. Redacting first collapses any matched
    secret to `***` before its bytes can straddle the cut.

    The tail typically carries the actual failure (stack trace, assertion
    diff, linter summary); the head is build noise. Identical convention
    to `_format_stderr_diagnostics`.
    """
    if not text:
        return ""
    redacted = _credentials.redact_secrets(text)
    if len(redacted) <= _models._VERIFY_OUTPUT_BUDGET:
        return redacted
    return redacted[-_models._VERIFY_OUTPUT_BUDGET:]
