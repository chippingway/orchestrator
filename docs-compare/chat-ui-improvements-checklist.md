# Chat UI applicability

Chipping Orchestrator has no native Chat UI, Electron renderer, mobile conversation surface, or streaming chat
protocol. AO's Chat UI checklist therefore has no component-by-component implementation counterpart here.

The documented multi-turn interactions use GitHub issue comments:

- `workflow:question` resumes a pinned developer session after a trusted human answer;
- `workflow:discussion` alternates a pinned agent session and trusted human turns;
- discussion publication requires explicit human confirmation and produces a plan-only pull request; and
- receipts, parks, mentions, and retry commands remain visible in the issue thread.

GitHub supplies rendering, timestamps, unread behavior, editing, scrolling, and accessibility for those conversations.
The orchestrator owns only trust filtering, durable cursors/session facts, transition rules, and posted messages. The
optional Streamlit tools are read-only analytics viewers rather than conversation clients.

Sources: [`../docs/workflow/conversations.md`](../docs/workflow/conversations.md),
[`../docs/state-machine/conversation-stages.md`](../docs/state-machine/conversation-stages.md), and
[`../docs/observability/analytics-dashboard.md`](../docs/observability/analytics-dashboard.md).

