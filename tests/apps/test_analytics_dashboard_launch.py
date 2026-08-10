# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Direct-script launch shape for the analytics page's entry path."""
from __future__ import annotations

import os
import runpy
import sys
import tempfile
import unittest
from importlib import import_module
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

from tests.observability.dashboard.reload_helpers import (
    hermetic_environment as _hermetic_env,
)
from tests.apps.script_launch_helpers import (
    clear_modules as _drop_modules,
    drop_repo_root as _strip_repo_root,
    script_launch_sandbox as _launch_sandbox,
)


_ORCH = "orchestrator"

_ORCH_PREFIX = f"{_ORCH}."

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The file a launcher is pointed at, kept as a one-entry inventory because the
# cases below are written against a launch shape rather than one path.
_SCRIPTS = ((_ORCH, "apps", "analytics_dashboard.py"),)

_LAUNCH_MODULES = (f"{_ORCH}.apps.analytics_dashboard",)

# What the shim exists for: a name under the package that resolves only once
# the repo root is on `sys.path`, and that a decoy parent cannot answer for.
_COMPOSED = f"{_ORCH}.observability.dashboard.page_pipeline"

# The bare name the entry path may reach its shim through under a script
# launch. It may not be probed on the package path, where a stray copy of it
# would shadow the real helper.
_BARE_HELPERS = ("bootstrap",)

_STRAY_HELPER = "raise RuntimeError('a stray helper must not be imported')\n"

# The group the entry path may not cost at import, and the chart owners in
# front of Plotly that reaching them lazily is what keeps out.
_DASHBOARD_GROUP = ("pandas", "plotly", "streamlit")

_CHARTS = f"{_ORCH}.observability.dashboard.charts"


def _is_launch_world(name: str) -> bool:
    """Whether a loaded module belongs to the world one launch rebuilds.

    The parent packages are in it, not only the entry path: a rebuilt app is
    bound as an attribute of whichever `orchestrator.apps` object is current
    when it is imported, so restoring the entry alone would leave that
    attribute answering with the throwaway one for the rest of the session.
    """
    return name == _ORCH or name.startswith(_ORCH_PREFIX) or name in _BARE_HELPERS


def _is_dependency_world(name: str) -> bool:
    """Whether a loaded module is one the dependency check rebuilds.

    The optional group is in it because an earlier test that reached one of
    those packages would otherwise decide this one, and because dropping it
    for the import under test has to be undone for whoever runs next.
    """
    return _is_launch_world(name) or name.partition(".")[0] in _DASHBOARD_GROUP


class ScriptPathLaunchTest(unittest.TestCase):
    """Guard `streamlit run` on the page's file.

    Streamlit executes the file as a top-level script via `runpy` with only
    the *script's* directory on `sys.path` (not the repo root), so a naked
    relative import or a bare absolute import without the shim raises
    `ImportError` before any Streamlit code can render. We reproduce that
    launch shape here without pulling Streamlit in (the dashboard group is
    opt-in): strip the repo root, insert the script's dir, then `runpy` the
    file with a non-`__main__` run name so `main()` is not invoked.
    """

    def test_each_target_runs_off_the_script_dir(self) -> None:
        for parts in _SCRIPTS:
            with self.subTest(script=parts[-1]):
                self.assertIn("main", self._launched(parts))

    def test_a_stale_parent_cannot_shadow_the_repo(self) -> None:
        # With only the script's directory on `sys.path`, importing
        # `orchestrator.<x>` before the shim prepends the repo root would bind
        # the parent package to whatever stale copy is importable and route
        # every later absolute import through it. The shim adds the repo root
        # without importing `orchestrator.*` first, so the real package
        # resolves even with a decoy parent behind the script dir on the path.
        for parts in _SCRIPTS:
            with self.subTest(script=parts[-1]):
                with tempfile.TemporaryDirectory() as decoy_root:
                    # A bare `orchestrator` package with none of the real
                    # submodules, standing in for a stale install.
                    decoy_package = Path(decoy_root) / _ORCH
                    decoy_package.mkdir()
                    (decoy_package / "__init__.py").write_text("")
                    self.assertIn("main", self._launched(parts, decoy_root))

    def _launched(
        self,
        parts: tuple[str, ...],
        decoy_root: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run one target the way a launcher does, and read the shim back."""
        script = _REPO_ROOT.joinpath(*parts)
        with _launch_sandbox(_is_launch_world):
            _strip_repo_root(_REPO_ROOT)
            if decoy_root is not None:
                sys.path.insert(0, decoy_root)
            sys.path.insert(0, str(script.parent))
            _drop_modules(_is_launch_world)
            namespace = runpy.run_path(str(script), run_name="not_main")
            # The composition the passes defer is what the shim is for, so
            # resolving it is what says the repo root landed -- and, with a
            # decoy parent on the path, that the real package answered.
            self.assertEqual(import_module(_COMPOSED).__name__, _COMPOSED)
            return namespace


class StrayHelperShadowTest(unittest.TestCase):
    """A package import resolves its shim qualified, never by bare name."""

    def test_a_stray_helper_stays_unimported(self) -> None:
        # An unrelated top-level `bootstrap` earlier on `sys.path` would
        # otherwise shadow the real helper or fail the import outright, so no
        # bare name may be probed on the package path.
        for module_name in _LAUNCH_MODULES:
            with self.subTest(module=module_name):
                self._imported_past_the_strays(module_name)

    def _imported_past_the_strays(self, module_name: str) -> None:
        """Import one entry path with every bare name booby-trapped."""
        with _launch_sandbox(_is_launch_world):
            with tempfile.TemporaryDirectory() as stray_dir:
                for helper in _BARE_HELPERS:
                    # A stray that detonates on import, so a bare probe fails
                    # loudly instead of silently binding the wrong helper.
                    stray = Path(stray_dir) / f"{helper}.py"
                    stray.write_text(_STRAY_HELPER)
                sys.path.insert(0, stray_dir)
                _drop_modules(_is_launch_world)
                self.assertTrue(hasattr(import_module(module_name), "main"))
                for helper in _BARE_HELPERS:
                    self.assertNotIn(helper, sys.modules)


class LazyDependencyTest(unittest.TestCase):
    """Naming the entry path costs neither the group nor the chart owners.

    The polling tick loads `orchestrator.*` modules at process start, so an
    entry path that imported Streamlit -- or a chart owner, and Plotly behind
    it -- at module scope would put the opt-in `dashboard` group behind every
    orchestrator deployment. Composing inside the passes is that boundary.
    """

    def test_the_path_costs_no_dashboard_group(self) -> None:
        for module_name in _LAUNCH_MODULES:
            with self.subTest(module=module_name):
                self._imported_hermetically(module_name)

    def _imported_hermetically(self, module_name: str) -> None:
        """Import one entry path into a world holding none of the optionals."""
        with _launch_sandbox(_is_dependency_world):
            with patch.dict(os.environ, _hermetic_env(), clear=True):
                _drop_modules(_is_dependency_world)
                import_module(module_name)
                for absent in (*_DASHBOARD_GROUP, _CHARTS):
                    self.assertNotIn(absent, sys.modules)


if __name__ == "__main__":
    unittest.main()
