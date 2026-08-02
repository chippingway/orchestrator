# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Historical import site for the connection, filter, and metadata reads.

The scope a read is issued inside, the filters a cache key is read back as, and
the extent and vocabulary a page opens on are three owners' own objects. A
caller that names this module -- the read wrappers beside it, the hub in front
of them, and every historical `dashboard.<name>` import through that hub --
reaches what those owners decided rather than a copy of any of them, so a page
and the owners cannot answer differently.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import (
    filter_binding,
    scoped_reads,
    static_metadata,
)


STATIC_METADATA_TTL_SECONDS = static_metadata.STATIC_METADATA_TTL_SECONDS
_filter_list = filter_binding.filter_list
_scoped_read = scoped_reads.scoped_read
_read_data_extent = static_metadata.read_data_extent
_read_filter_options = static_metadata.read_filter_options
_read_static_metadata = static_metadata.read_static_metadata
_read_filter_kwargs = filter_binding.read_filter_kwargs
_read_filtered = filter_binding.read_filtered
