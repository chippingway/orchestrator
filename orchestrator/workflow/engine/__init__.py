# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Workflow engine owners.

Home for the tick loop, dispatch, and the shared-helper owners the stages
borrow from. Callers import the owner they need directly, so this initializer
binds nothing and an import pulls in only what the chosen owner itself needs.
"""
