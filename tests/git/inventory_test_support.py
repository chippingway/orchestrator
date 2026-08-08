# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Export-inventory enumeration shared by the git package's import guards."""
from __future__ import annotations

import importlib
from pathlib import Path

# Every immutable export inventory a package carries, which is where a name's
# resolution target is declared.
_INVENTORY_GLOB = "*_export_manifest.py"


def inventory_modules(package_name: str) -> tuple[str, ...]:
    """Import paths of every export inventory one package carries."""
    package_root = Path(importlib.import_module(package_name).__file__).parent
    return tuple(sorted(
        ".".join(path.relative_to(package_root.parent).with_suffix("").parts)
        for path in package_root.rglob(_INVENTORY_GLOB)
    ))
