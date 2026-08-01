# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Trajectory viewer owners.

Home of the second Streamlit page -- the file-backed viewer that reads the
trajectory JSONL directly, usage and cost included, and needs no Postgres: the
pure filter and summary read model, the run views built from it, and the HTML a
page is rendered from.

The record side arrives first. ``constants`` owns what one line is recognized,
bracketed, and dismissed by; ``coercion`` owns the narrowing every untyped
field passes through, so a hand-edited or older record costs a smaller row
rather than a failed read. ``models`` owns the frozen pieces a record is read
back as -- the step, the timeline entry, and the two usage summaries -- with
the constructor signatures and the historical module identity they are
published under. ``runs`` is the record itself, and it defines no view of its
own: ``usage_views`` answers for a run's tallies and its money, and
``timeline_views`` for the one ordered sequence it renders as, the labels it is
picked by, and the tells that mark it a fixture. ``parsing`` is what turns a
decoded line into one of those records -- the event it is accepted for, the
position it is stamped with, and the narrowing every field goes through.

The read over them arrives with it. ``reading`` is the whole of one pass over
the file: the blank, malformed, and foreign lines skipped rather than raised
over, the newest-first order the records come back in, and the missing file
answered silently where any other read error is warned about first.
``log_paths`` answers *which* file that is -- read off the settings holder a
caller hands in, so two reader worlds stay apart -- and what an operator gets
instead when the opt-in sink was never switched on.

What a page then narrows that read to arrives last, and none of it opens a
file. ``filter_models`` holds the shapes one request is spelled, narrowed, and
answered in; ``filter_values`` a single value -- the distinct ones a dropdown
is offered, the empty selection that constrains nothing, and the text a needle
is compared against; ``filtering`` which runs one request keeps, in the order
the read already handed them over; and ``summaries`` the headline counts the
survivors are totalled into. The three that answer over runs name the record at
import even though none of them builds one: what they are annotated in is a
published surface, and a name bound only for a type checker is a
``get_type_hints`` that raises for the caller reading it back.

What that read is then drawn as begins to arrive after it, and none of it
imports Streamlit either. ``css`` is the stylesheet this page adds on top of
the chrome both pages share, written against the same geometry owner the
analytics page is set in; ``summary_html`` the banner and the five tiles a
whole read is summarized in, built off the summary rather than the runs;
``run_html`` the three renderings one run is identified by -- the metadata
grid, the overview row, and the picker label; ``usage_html`` what a run cost,
tallied once for the whole run and once per assistant turn, with the note
saying why the authoritative figure and the estimates beneath it need not sum;
and ``timeline_html`` the header one entry is read by and the decision of which
entry a usage strip belongs above. What a caller passes into any of them is
escaped before it reaches the markup, because a page writes these with
``unsafe_allow_html=True`` and every value in them is record text this viewer
does not own.

Callers import the owner they need, so this initializer binds nothing, and
Streamlit stays behind a function-local import for the same reason it does
in ``dashboard`` -- with one more: the read model here is pure, and its
value is that it stays importable, and testable, in an install carrying no
viewer dependencies at all.
"""
