# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The root package publishes its version and nothing else."""
from __future__ import annotations

import subprocess
import sys
import unittest
from importlib import import_module

from orchestrator import __version__ as imported_version

_ORCHESTRATOR_PACKAGE = import_module("orchestrator")


class PackageMetadataTest(unittest.TestCase):
    """`__version__` is the whole published surface, `__all__` names just it.

    Everything a caller runs lives under a subpackage they import directly, so
    a name added here would be a second site for an owner to answer on -- and
    would put that owner's graph behind the `import orchestrator` every launch
    form already pays for.
    """

    def test_version_import_surface(self) -> None:
        self.assertEqual(_ORCHESTRATOR_PACKAGE.__version__, imported_version)
        self.assertIn("__version__", _ORCHESTRATOR_PACKAGE.__dir__())

    def test_wildcard_import_exposes_only_the_version(self) -> None:
        command = "from orchestrator import *; print(__version__)"
        completed = subprocess.run(
            [sys.executable, "-c", command],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.stdout.strip(), imported_version)
        self.assertEqual(_ORCHESTRATOR_PACKAGE.__all__, ("__version__",))


if __name__ == "__main__":
    unittest.main()
