# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the orchestrator's per-stage handlers.

Every stage now lives as a subpackage of responsibility-named owners under
`orchestrator.workflow.stages`; `decomposition`, `implementing`,
`documenting`, `validating`, `in_review`, `fixing`, `conflicts`, and
`question` have all gone. A stage still reached for under its historical
spelling keeps the module it vacated here as a temporary forwarder that reads
every name back off those owners rather than rebuilding one, so this package
stays the import site those callers and their patches already name. The
forwarder goes once they name the owner instead, which `validating`,
`in_review`, `question`, `decomposition`, `implementing`, and `conflicts` have
already outlived: nothing here answers for those stages.

Orchestrator code itself no longer reads through here. The dispatcher
(`orchestrator.workflow.engine.dispatch`) owns the label->handler routing and
imports the module its table names for a label at call time, and that table --
like the same-tick start in `workflow/engine/pickup.py` -- names the owner a
handler lives on, so intercepting one means patching there and not here.
`orchestrator.workflow` also re-exports each handler under its original
`_handle_*` name, straight off the owner, so direct test references and
stage-to-stage calls keep working.
"""
