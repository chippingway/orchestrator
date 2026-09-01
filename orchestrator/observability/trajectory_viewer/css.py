# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""The stylesheet this page adds on top of the chrome both pages share.

Almost every rule is scoped to an ``orch-traj-*`` class only this page emits,
so the sheet describes what is different and nothing else: the metadata grid,
the chips, the run table, the step headers, and the per-turn usage strip. The
two that are not scoped that way re-declare the shared chrome's own
``.orch-kpis`` grid, because this page carries five tiles where the analytics
one carries four. They win the cascade on injection order -- the page writes
the shared stylesheet first and this one after it -- rather than on
specificity, which is why the narrow-viewport reflow has to be restated
alongside the column count.

The text colors are read as CSS variables the shared stylesheet declares, so a
palette edit moves both pages at once. Two things cannot be read that way. The
font stacks are interpolated from the geometry owner both pages are set in,
because no variable was ever declared to hold one. And the translucent washes
behind the badges, the fixture tag, and the cache-hit pill are literal
``rgba()``, because a variable holds an opaque hex that a rule has no way to
add an alpha channel to. Each of those washes is one of the declared colors
restated at low alpha, which makes them the one place a palette edit has to be
mirrored by hand.
"""
from __future__ import annotations

from orchestrator.observability.dashboard import tokens

EXTRA_CSS = f"""
<style>
  .orch-traj-meta {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px; margin: 4px 0 14px;
  }}
  .orch-traj-meta-item {{
    border: 1px solid var(--orch-border); border-radius: 10px;
    padding: 9px 12px; background: var(--orch-card);
  }}
  .orch-traj-meta-item .k {{
    color: var(--orch-muted-soft); font-size: 11px; font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.05em;
  }}
  .orch-traj-meta-item .v {{
    color: var(--orch-ink); font-size: 14px; margin-top: 2px;
    font-family: {tokens.MONO_FONT_FAMILY}; word-break: break-word;
  }}
  .orch-traj-chips {{
    display: flex; flex-wrap: wrap; gap: 6px; margin: 2px 0 12px;
  }}
  .orch-traj-chips .lbl {{
    color: var(--orch-muted); font-size: 12px; font-weight: 500;
    margin-right: 4px; align-self: center;
  }}
  .orch-traj-chip {{
    background: var(--orch-chip); color: var(--orch-ink);
    border: 1px solid var(--orch-border); border-radius: 999px;
    padding: 2px 10px; font-size: 12px;
    font-family: {tokens.MONO_FONT_FAMILY};
  }}
  /* Empty-state marker: dims and dashes the chip so a "none" reads as
     "no skill fired" rather than a skill literally named none. */
  .orch-traj-chip.none {{
    background: transparent; color: var(--orch-muted-soft);
    border-style: dashed; font-style: italic;
  }}
  .orch-traj-table {{
    width: 100%; border-collapse: collapse; font-size: 12.5px;
    font-family: {tokens.FONT_FAMILY};
  }}
  .orch-traj-table th {{
    text-align: left; color: var(--orch-muted); font-weight: 500;
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
    padding: 6px 10px; border-bottom: 1px solid var(--orch-border);
  }}
  .orch-traj-table td {{
    padding: 6px 10px; border-bottom: 1px solid var(--orch-grid);
    color: var(--orch-ink);
  }}
  .orch-traj-table td.num {{
    text-align: right; font-family: {tokens.MONO_FONT_FAMILY};
  }}
  .orch-traj-step {{
    display: flex; align-items: center; gap: 10px;
    margin: 10px 0 4px;
  }}
  .orch-traj-step-idx {{
    color: var(--orch-muted-soft); font-size: 12px;
    font-family: {tokens.MONO_FONT_FAMILY}; min-width: 24px;
  }}
  .orch-traj-badge {{
    font-size: 11px; font-weight: 600; padding: 2px 9px;
    border-radius: 6px; white-space: nowrap;
    font-family: {tokens.MONO_FONT_FAMILY};
  }}
  .orch-traj-badge.call {{
    background: rgba(91,84,224,.12); color: var(--orch-accent);
  }}
  .orch-traj-badge.result {{
    background: rgba(26,163,154,.14); color: var(--orch-cache);
  }}
  .orch-traj-badge.prompt {{
    background: rgba(86,93,114,.12); color: var(--orch-muted);
  }}
  .orch-traj-badge.assistant {{
    background: rgba(224,145,58,.14); color: var(--orch-output);
  }}
  .orch-traj-badge.user {{
    background: rgba(91,108,240,.12); color: var(--orch-input);
  }}
  .orch-traj-badge.output {{
    background: rgba(47,158,107,.14); color: var(--orch-success);
  }}
  .orch-traj-fixture-tag {{
    display: inline-block; margin-left: 6px;
    background: rgba(224,145,58,.14); color: var(--orch-warn);
    border: 1px solid rgba(224,145,58,.30); border-radius: 999px;
    padding: 0 7px; font-size: 10px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.04em;
    font-family: {tokens.MONO_FONT_FAMILY};
  }}
  .orch-traj-table tr.fixture td {{ color: var(--orch-muted-soft); }}
  .orch-traj-step-name {{
    color: var(--orch-ink); font-weight: 600; font-size: 13px;
    font-family: {tokens.MONO_FONT_FAMILY};
  }}
  .orch-traj-step-id {{
    color: var(--orch-muted-soft); font-size: 11px;
    font-family: {tokens.MONO_FONT_FAMILY}; margin-left: auto;
  }}
  /* Run-level usage summary + per-turn strip -------------------- */
  /* The cost chip in the run-usage row is the headline number, so it
     carries the accent border to read louder than the token chips. */
  .orch-traj-chip.cost {{
    border-color: var(--orch-accent); font-weight: 600;
  }}
  .orch-traj-usage-note {{
    color: var(--orch-muted-soft); font-size: 11.5px;
    margin: 0 0 12px; font-family: {tokens.FONT_FAMILY};
  }}
  .orch-traj-turn {{
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
    margin: 14px 0 2px; padding: 5px 11px;
    border: 1px solid var(--orch-border); border-radius: 8px;
    background: var(--orch-chip); color: var(--orch-muted);
    font-size: 11.5px; font-family: {tokens.MONO_FONT_FAMILY};
  }}
  .orch-traj-turn .orch-traj-turn-model {{
    color: var(--orch-ink); font-weight: 600;
  }}
  .orch-traj-usage-sep {{ color: var(--orch-muted-soft); }}
  .orch-traj-cache-hit {{
    background: rgba(26,163,154,.14); color: var(--orch-cache);
    border-radius: 999px; padding: 1px 8px;
    font-size: 10px; font-weight: 600; letter-spacing: 0.02em;
  }}
  /* Five KPI tiles on this page (runs / issues / repos / tool calls /
     total cost); re-declare the shared chrome's <=1080px two-column
     reflow so the added tile does not force five across on a narrow
     viewport. Both rules follow `PAGE_CSS`, so they win the cascade. */
  .orch-kpis {{ grid-template-columns: repeat(5, 1fr); }}
  @media (max-width: 1080px) {{
    .orch-kpis {{ grid-template-columns: repeat(2, 1fr); }}
  }}
</style>
"""
