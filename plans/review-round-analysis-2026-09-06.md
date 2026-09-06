Analysis of issues with the most review rounds — 7 August–6 September 2026

Working note for further checking and possible improvements. Findings and issue statuses reflect the analysis cutoff
below; recommendations remain proposals.

The strongest recurring cause was an incomplete design for how evidence and state survive across component boundaries,
followed by fixes that addressed one reported path at a time. Decomposition amplified that problem: some children
combined several substantial systems, while others separated pieces of one transaction without an independently
reviewable acceptance boundary. Tests often confirmed those local assumptions instead of exercising the real
producer/consumer or dispatcher/recovery path.

**Scope and counting.** This covers every repository represented in the orchestrator's last 30 days of analytics:
**2026-08-07 07:21:43 UTC through 2026-09-06 07:21:43 UTC**, equivalent to 14:21:43 local time at both endpoints. It
selects reviewer activity during the window, regardless of issue creation or closure date. Historical
`geserdugarov/agent-orchestrator` records are normalized to `chippingway/orchestrator`, confirmed by GitHub's canonical
issue URLs. Local analytics contain 823 reviewer invocations across 175 issues; the median is two invocations. No exact
duplicate agent-exit records or repeated reviewer session IDs were found. Two malformed source rows were skipped. This
is a ranking of observed orchestrator reviews, not a census of every human or external-bot review on GitHub.

The six largest cases account for **219/823 attempts (26.6%)**: 218 completed verdicts, comprising 212 change requests
and six approvals, plus one interrupted invocation. Their reviews and implementations all occurred within the selected
window. Counting only the stored `review_round` would hide most of the work: #1464 completed five sequences of counters
0–9 and received four explicit grants of ten more rounds. Other resets can come from rebases or handoffs, so a reset
alone does not establish a particular cause. [Example
reset](https://github.com/chippingway/orchestrator/issues/1464#issuecomment-5460022368).

The following ten are ordered by reviewer attempts. “Completed” includes approvals. The additions column is the
final/current PR diff and includes source, tests, and documentation; it is not the initial implementation size or total
churn.

| Issue | Attempts | Completed | Failed without verdict | PR additions | Main diagnosis |
|---|---:|---:|---:|---:|---|
| [orchestrator #1464 — cumulative PR gate](https://github.com/chippingway/orchestrator/issues/1464) | 50 | 50 | 0 | 18,462 | Scope crossed sibling boundaries; publication transaction designed incrementally |
| [quake-rust #4 — builds, provenance, preflight](https://github.com/geserdugarov/quake-rust/issues/4) | 38 | 38 | 0 | 24,299 | Overloaded child; real tool behavior and producer/validator agreement insufficiently tested |
| [orchestrator #1322 — discussion plan publication](https://github.com/chippingway/orchestrator/issues/1322) | 37 | 36 | 1 | 11,940 | Incomplete publication identity, recovery, and implementation-handoff model |
| [orchestrator #1408 — irreversible cancellation](https://github.com/chippingway/orchestrator/issues/1408) | 33 | 33 | 0 | 14,146 | Cancellation did not durably control every active worker and side-effect boundary |
| [quake-rust #7 — measurement, guards, statistics](https://github.com/geserdugarov/quake-rust/issues/7) | 33 | 33 | 0 | 18,521 | Measurement ownership and provenance disagreed with actual backends |
| [orchestrator #1410 — activate late splitting](https://github.com/chippingway/orchestrator/issues/1410) | 28 | 28 | 0 | 9,334 | Final integration inherited unresolved transaction invariants; documentation added tail rounds |
| [orchestrator #1471 — conflict publication gate](https://github.com/chippingway/orchestrator/issues/1471) | 20 | 13 | 7 | 3,039 | Recovery/receipt defects plus a substantial independent CLI failure component |
| [orchestrator #1407 — snapshot reclamation](https://github.com/chippingway/orchestrator/issues/1407) | 19 | 19 | 0 | 5,776 | Ledger completeness, consumer reopening, concurrent state writes, and uncertain reads |
| [orchestrator #1486 — artifact cleanup](https://github.com/chippingway/orchestrator/issues/1486) | 18 | 18 | 0 | 6,396 | Durable cleanup obligations and destructive-boundary races; eventually split into four children |
| [orchestrator #1608 — automatic-rebase recovery](https://github.com/chippingway/orchestrator/issues/1608) | 15 | 15 | 0 | 7,370 | Partial records and crash ordering; still unfinished at the cutoff |

**#1464: the clearest decomposition and review-scope mismatch.** The parent's ten-child split assigned exact accepted
publication to #1466, supersession to #1467, and individual publication routes to #1468–#1471. Nevertheless, #1464's
first reviews required routing those other paths, and review invocation 39 still required implementing post-publication
supersession. Those are recognizable sibling responsibilities, not merely additional tests for the core measurement
helper. The original PR description names two integration points; the final diff spans 196 files. This is direct
evidence that the decomposition did not remain an effective review boundary. [Parent
split](https://github.com/chippingway/orchestrator/issues/1461#issuecomment-5451260229), [first
review](https://github.com/chippingway/orchestrator/pull/1474#issuecomment-5452988911), [invocation
39](https://github.com/chippingway/orchestrator/pull/1474#issuecomment-5467282768).

There were also real defects within the work undertaken. The gate initially returned a boolean and discarded the
candidate/head identities that publication needed. Subsequent iterations added authorization, leases, receipts, and
stage bookkeeping, repeatedly clearing one before its successor was durable. Invocation 25 still found lost completion
bookkeeping after a successful push; invocation 49 still found an unsafe crash between recording the push and checking
the checkout. My diagnosis is a missing complete publication transaction model, compounded by work expanding into
downstream children. [Lost bookkeeping](https://github.com/chippingway/orchestrator/pull/1474#issuecomment-5463180634),
[late crash defect](https://github.com/chippingway/orchestrator/pull/1474#issuecomment-5468737446).

**Quake #4: broad scope and tests disconnected from real artifacts.** One child owned Rust, C++, and FAISS builds,
toolchain/environment capture, source and binary identity, host preflight, and a separate manifest validator. Review
repeatedly found that the writer's real output and the reader's accepted schema disagreed. At invocation 18, a Rust
build still invoked the resolved Cargo binary with a rustup-only selector. Invocation 20 found the same mistake in
preflight. At invocation 25, actual recipe records could not pass their own verifier; the tests synthesized commands
from the validator schema and concealed the discrepancy. This is particularly strong evidence of patching only the
reported location and testing internal consistency without realistic integration. [Cargo
build](https://github.com/geserdugarov/quake-rust/pull/14#issuecomment-5330466770), [Cargo
preflight](https://github.com/geserdugarov/quake-rust/pull/14#issuecomment-5331746937), [producer/reader
mismatch](https://github.com/geserdugarov/quake-rust/pull/14#issuecomment-5333277321).

The same pattern extended to FAISS linkage and command parsing: a policy demanded linkage combinations that genuine
generic and AVX2 extensions do not have, while another iteration could not parse Cargo's real tree output. My diagnosis
is both an oversized issue and inadequate grounding in actual tool behavior. Independent parser tests were insufficient
for a build/provenance system. [Real linkage
rejected](https://github.com/geserdugarov/quake-rust/pull/14#issuecomment-5334307184), [real Cargo output
rejected](https://github.com/geserdugarov/quake-rust/pull/14#issuecomment-5335004153).

**#1322: file validation was implemented before publication identity and recovery were settled.** The first review found
that any plan-shaped commit could be attributed to the decomposer, deleting an existing plan could satisfy the path
check, and a failed status read could look clean. Later reviews found validated SHA versus pushed HEAD mismatches and
retries that could overwrite a human's plan amendment. These follow from missing distinctions between an authorized
round, a validated candidate, a pending publication, a landed PR, and a plan being handed to an implementer. [Initial
gaps](https://github.com/chippingway/orchestrator/pull/1329#issuecomment-5313352629), [unbound
publication](https://github.com/chippingway/orchestrator/pull/1329#issuecomment-5313751358), [amendment
overwritten](https://github.com/chippingway/orchestrator/pull/1329#issuecomment-5317144283).

By invocation 34, the review still reproduced interrupted handoffs that could overwrite amendments or treat a merged
plan as completed implementation. This is principally an initial state/identity design problem, with a broad
publication-plus-handoff boundary increasing the number of cases. The one failed reviewer process does not explain the
other 36 completed reviews. [Late handoff
defects](https://github.com/chippingway/orchestrator/pull/1329#issuecomment-5327605969).

**#1408: cancellation was added as cleanup behavior before it became a durable execution barrier.** The first review
showed that a reopened cancelled owner could resume and that generic cleanup modified children despite the explicit
untouched-children requirement. A helper-level test missed real dispatcher behavior. Later fixes introduced an in-memory
close latch, which still could not stop an active worker or survive restart. Much later, accepted-but-never-started
tasks and generation retirement could still lose observed cancellation. My diagnosis is that a cross-cutting lifecycle
requirement was handled through local guards rather than a durable, cycle-scoped protocol governing all effect
boundaries. [Initial dispatcher gap](https://github.com/chippingway/orchestrator/pull/1425#issuecomment-5388023956),
[memory-only latch](https://github.com/chippingway/orchestrator/pull/1425#issuecomment-5390575290), [restart/retirement
gaps](https://github.com/chippingway/orchestrator/pull/1425#issuecomment-5396088975), [late retirement
race](https://github.com/chippingway/orchestrator/pull/1425#issuecomment-5399196031).

**Quake #7: the measurement model did not match where work actually ran.** Early reviews found that a 64-query payload
could be reported as 128 queries and that guard/RSS collection inspected the controller while Quake ran in a child
process. Another test fixture reproduced the implementation's incorrect `/proc` field offset. Later reviews found
unrelated configurations could share measurement evidence, and statistics could accept caller-supplied bounds without
deriving them from retained samples. The recurring problem was weak binding between engine, worker, execution mode,
configuration, raw observations, and result. [Payload
identity](https://github.com/geserdugarov/quake-rust/pull/17#issuecomment-5339641457), [wrong process
measured](https://github.com/geserdugarov/quake-rust/pull/17#issuecomment-5340757647), [fixture repeats
error](https://github.com/geserdugarov/quake-rust/pull/17#issuecomment-5341018098), [unverified
statistics](https://github.com/geserdugarov/quake-rust/pull/17#issuecomment-5349378369).

This child combined measurement, operating-system guards, statistical inference, and finalist selection. Its tests
needed representative worker/FAISS behavior much earlier. Invocation 28 still found valid real FAISS Flat construction
rejected by an assumed seven-thread requirement; invocation 31 found construction memory depending on earlier builds and
serialized artifacts not bound to the measured build. [Real FAISS
mismatch](https://github.com/geserdugarov/quake-rust/pull/17#issuecomment-5352267270), [build identity and
memory](https://github.com/geserdugarov/quake-rust/pull/17#issuecomment-5367279893).

**#1410: “wire the feature” concealed unresolved integration architecture.** This was the last child of a ten-part
feature split. Review found a recorded candidate replaced by current HEAD, checked identities discarded before push, and
approval state retired before publication became durable. Those are full transaction concerns, so the final wiring step
still had to design core behavior. Invocations 26 and 27 were then documentation-only: the authoritative descriptions
had not caught up with earlier fixes. [Parent
split](https://github.com/chippingway/orchestrator/issues/1400#issuecomment-5369274869), [first
review](https://github.com/chippingway/orchestrator/pull/1445#issuecomment-5410993253), [publication
identity](https://github.com/chippingway/orchestrator/pull/1445#issuecomment-5412302435), [durability
gap](https://github.com/chippingway/orchestrator/pull/1445#issuecomment-5415293155), [documentation round
26](https://github.com/chippingway/orchestrator/pull/1445#issuecomment-5423721520), [documentation round
27](https://github.com/chippingway/orchestrator/pull/1445#issuecomment-5423957379).

**Other causes that should remain separate.** #1471 incurred seven reviewer CLI exits with code 1 and no verdict, in
addition to 11 change-request verdicts and two approvals. They were not timeouts. The captured stderr does not establish
why the CLI failed, so attributing them to provider outages, quota, or implementation quality would be speculation.
[Failure record](https://github.com/chippingway/orchestrator/issues/1471#issuecomment-5474764651).

#1486 received 18 change requests and no approval for its original PR. After ten `single` decisions on oversized
candidates, the eleventh decomposer run split it into proof/outcome, durable-obligation, worktree-removal, and
branch-cleanup children. Its original PR was superseded; parent closure should not be read as that original
implementation passing review. #1608 was also unresolved at the cutoff, with 15 change requests and ten
size-adjudication runs, and its next candidate held at 7,576 additions. These show repeated size adjudication adding
another loop around an already lengthy review cycle. [Actual cleanup
split](https://github.com/chippingway/orchestrator/issues/1486#issuecomment-5525597417), [held rebase
candidate](https://github.com/chippingway/orchestrator/issues/1608#issuecomment-5555731742), [retry
cap](https://github.com/chippingway/orchestrator/issues/1608#issuecomment-5555751305).

There is some review-process overhead beyond correctness. #1464 invocation 35 requested comment wording alone, yet later
invocations still discovered serious defects. That is evidence of uneven discovery and a limited value to treating each
round as a fresh checklist pass. It does not establish that the substantive findings were unnecessary. [Style-only
round](https://github.com/chippingway/orchestrator/pull/1474#issuecomment-5466785972).

**Changes I would prioritize.**

1. Give each child explicit acceptance criteria, deferred sibling responsibilities, and the contract it provides to
  dependants. Review against that boundary. For a shared primitive, keep it safely dormant until integration; for a
  shipped behavior, include a complete use case and its recovery path. #1464 shows why the distinction must be explicit.
2. Before coding stateful publication or cleanup, define the durable states, exact identities, external effects,
  recovery entry points, and obligations that survive every crash boundary. Check both ordinary execution and restart
  through the real dispatcher. Treat missing, malformed, unreadable, and absent evidence as distinct states.
3. Require a small representative integration proof early for external tools and benchmarks: real CLI argument/output
  checks, genuine recipe output consumed by its validator, a worker-process resource violation, and representative FAISS
  mode behavior. Fixtures should be independently grounded in those observations.
4. When a review finds a broken invariant, audit every producer and consumer of that invariant in the same fix. The
  repeated Cargo error and repeated publication-SHA loss show the cost of fixing only the named location.
5. Introduce an architecture/scope checkpoint after roughly 3–5 substantive unsuccessful reviews, before granting
  another block of ten. This is a proposed operating rule, not a measured optimal threshold. Existing run budgets and
  size caps bound spending but do not diagnose why work is failing to converge.
6. Finish a coordinated documentation pass after behavior stabilizes, and make the final review cover both the code and
  its actual recovery behavior. Track change-request verdicts, approvals, failed reviewer attempts, cap grants, and
  size-adjudication runs separately.

**Evidence and limits.** Counts come from the local analytics sink; diagnoses were checked against original issue
bodies, decomposition comments, initial PR implementation summaries, final PR metadata, and all recorded reviewer
verdicts for the ten cases above. Root-cause labels are qualitative inferences, not experimentally measured causal
percentages. Historical reviewer reproductions were read, not rerun against today's changed code. The analytics file
spans the complete requested window, but any run never recorded by the observation-only sink cannot be recovered from
this count. Current/merged diff sizes do not prove how large an initial implementation was.

**Follow-up checks before selecting improvements.**

- [ ] Recheck the linked review findings against current code and record which causes still recur; historical defects
  may already be fixed.
- [ ] For #1464, compare the child and sibling acceptance criteria with the blocking review comments, then decide how
  implementer and reviewer prompts should preserve those boundaries.
- [ ] Compare a sample of issues completed in one or two reviews with these outliers, controlling where possible for
  feature size and integration complexity; this analysis selected the outliers and cannot establish causal percentages.
- [ ] Audit whether existing tests exercise real dispatcher/restart paths and actual producer/consumer compatibility for
  the publication, cancellation, and benchmark cases.
- [ ] Investigate #1471's reviewer failures independently using any retained CLI diagnostics; exit code 1 alone does not
  identify their cause.
- [ ] Check the current lifetime run budget and size-adjudication behavior before proposing additional controls,
  including what happened after the cutoff to #1608 and #1486's children.
- [ ] Trial an architecture/scope checkpoint on a small cohort and compare completed change-request rounds, reviewer
  failures, agent time, final diff size, and completion rate with the baseline above; record the chosen threshold as an
  experiment.
- [ ] Turn selected proposals into separately scoped issues with acceptance criteria and a validation method.

Optional local companion files: [ranked issues](../logs/review-analysis-2026-09-06/ranking.csv), [all counted reviewer
runs](../logs/review-analysis-2026-09-06/reviewer-runs.jsonl), [per-invocation source
links](../logs/review-analysis-2026-09-06/evidence-index.md), [machine-readable
methodology](../logs/review-analysis-2026-09-06/methodology.json). These files are gitignored local artifacts and may be
unavailable in another checkout. The principal findings, counts, methodology, limitations, and GitHub evidence links are
preserved in this note.
