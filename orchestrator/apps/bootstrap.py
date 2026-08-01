# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The repo-root `sys.path` shim every app here is script-launched through.

`streamlit run orchestrator/apps/trajectory_dashboard.py` executes the file as
a top-level script with no parent package: the launcher prepends the *script's
own directory* (`orchestrator/apps/`) to `sys.path`, not the repo root. Under
that layout a relative import raises `ImportError: attempted relative import
with no known parent package` and an absolute `from orchestrator import ...`
fails too, before any Streamlit code can render. Putting the repo root on the
path makes the absolute imports resolve in both launch modes.

An app selects how it reaches this module by launch mode, keyed on
`__package__`. A script launch (empty or absent `__package__`) uses the bare
`from bootstrap import ...`, which resolves this file out of the app's own
directory *without* importing the `orchestrator` package first -- importing the
parent before the repo root is on `sys.path` would bind it to whatever stale or
installed copy happens to be importable and route every later absolute import
through that. A package import uses the qualified
`from orchestrator.apps.bootstrap import ...`, so a stray top-level `bootstrap`
on `sys.path` cannot shadow it.

Nothing here is imported but the standard library, for the same reason: the
shim runs before the repo root is reachable, so anything it named would have to
resolve without it.
"""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_root_on_path(app_file: str) -> None:
    """Insert the repo root -- the grandparent of `apps/` -- onto `sys.path`.

    `app_file` is the calling app's `__file__`. The insert is idempotent: in
    the package-imported case the entry is already there and this is a no-op,
    so every app may call it unconditionally at its own import.
    """
    repo_root = Path(app_file).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
