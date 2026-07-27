# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Per-stage handlers for the orchestrator state machine.

The dispatcher (`orchestrator.workflow.engine.dispatch`) owns the
label->handler routing and imports the module its table names for a
label at call time; modules under this package own the bodies of those
handlers and their stage-private helpers. `orchestrator.workflow` also
re-exports each handler under its original `_handle_*` name so direct
test references and intra-handler calls keep working.

`orchestrator.workflow.stages` is where a stage facade moves once it has
an owner. The module it vacates stays here as a temporary forwarder that
reads every name back off that owner rather than rebuilding one, so this
package stays the import site historical callers and patches already
name until they name the owner instead.
"""
