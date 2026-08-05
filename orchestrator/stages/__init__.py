# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the orchestrator's per-stage handlers.

Every stage lives as a subpackage of responsibility-named owners under
`orchestrator.workflow.stages`; `decomposition`, `implementing`,
`documenting`, `validating`, `in_review`, `fixing`, `conflicts`, and
`question` have all gone, and each has outlived the temporary forwarder it
left behind here for the callers and patches that named this package. Nothing
answers for a stage here any more, so a name a stage owns has exactly one
module to resolve on.

Orchestrator code itself reads through the owners. The dispatcher
(`orchestrator.workflow.engine.dispatch`) owns the label->handler routing and
imports the module its table names for a label at call time, and that table --
like the same-tick start in `workflow/engine/pickup.py` -- names the owner a
handler lives on, so intercepting one means patching there.
`orchestrator.workflow` also re-exports each handler under its original
`_handle_*` name, straight off the owner, so direct test references and
stage-to-stage calls keep working.
"""
