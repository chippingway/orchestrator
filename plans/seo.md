# SEO Plan — `chippingway/orchestrator`

Two distinct surfaces need separate work:

1. **GitHub internal search** — repo name, description, topics, README text, stars, activity recency.
2. **External search + AI answer engines** — Google/Bing indexing, backlinks, docs site, how models describe the project when asked for alternatives.

---

## Current state audit

| Item | Current value | Assessment |
|---|---|---|
| Repo name | `orchestrator` | Too generic; hundreds of competing matches |
| README H1 | `chipping-orchestrator` | Mismatched with repo name |
| Clone directory | `chipping-orchestrator` | Third naming variant |
| About description | "Orchestrator for automated GitHub issue monitoring and agentic development across multiple repositories." | Accurate, keyword-poor |
| Topics | `agents`, `claude`, `claude-code`, `codex`, `codex-cli`, `github`, `openai`, `python` (8 of 20) | 12 slots unused |
| Website field | empty | Wasted; `docs/` tree exists but unpublished |
| Social preview | GitHub auto-generated | Weak share CTR |
| Releases | none (1,100 commits) | No indexed release pages, no version signal |
| PyPI | not published | `pyproject.toml` already present |
| Stars / forks | 10 / 1 | Distribution is the binding constraint |

---

## Priority 1 — Highest leverage

### 1.1 Rewrite the About description

This single field becomes `meta-description` and `og:description`, and GitHub search weights it heavily. Limit is ~350 characters. The current text never contains AI, Claude Code, Codex, coding agent, or pull request — the phrases people actually type.

Proposed replacement:

> Autonomous AI coding agent orchestrator. Watches GitHub issues, spawns Claude Code or Codex CLI in isolated git worktrees, opens PRs, and runs an independent reviewer pass. Self-hosted, Python, multi-repo.

### 1.2 Fill all 20 topic slots

Each `github.com/topics/<name>` page is independently indexed and browsable. Topics must be lowercase and hyphenated.

Keep the existing 8, add:

```
ai-agents
autonomous-agents
coding-agent
agentic-ai
llm
automation
developer-tools
github-issues
pull-request-automation
code-review
multi-agent
self-hosted
```

### 1.3 Publish `docs/` as a real docs site

Google heavily deprioritizes `github.com/.../blob/...` URLs, so the entire existing documentation tree is currently close to invisible to search.

Steps:

1. Add mkdocs (or Docusaurus) over the existing markdown in `docs/`.
2. Deploy via GitHub Pages using a workflow in `.github/workflows/`.
3. Set the resulting URL in the repo's **website** field.

Payoff: a dozen-plus indexable HTML pages able to rank on long-tail queries such as "claude code codex reviewer loop configuration" or "github issue to PR state machine labels". Likely the single biggest external win given how much documentation already exists.

### 1.4 Resolve the naming inconsistency

Three names are in play: `orchestrator` (repo), `chipping-orchestrator` (README H1), `chipping-orchestrator` (clone target).

Recommendation: rename the repo to `chipping-orchestrator`. GitHub issues permanent redirects from the old URL, so existing links and clones keep working. This aligns the repo with what the README and the docs already call the project, and escapes the generic `orchestrator` namespace.

---

## Priority 2 — README structure

Crawlers and AI answer engines read the top of the README first. The current H1 is a bare package name with no tagline.

### 2.1 Add a tagline under the H1

```markdown
# chipping-orchestrator

**Autonomous GitHub issue → PR pipeline for Claude Code and Codex CLI.**
```

### 2.2 Add a "when to use / when not to use" section

Explicit scope framing is what gets a project correctly cited rather than vaguely mentioned.

Sketch:

- **Use it when:** you have a `codex` or `claude` login, run solo or on a small team, want issue-to-PR autonomy without a separate planner, queue, or database, and want to merge by hand.
- **Don't use it when:** you need a hosted service, want auto-merge, cannot give an agent a host as the sandbox boundary, or need non-GitHub issue trackers.

### 2.3 Add a comparison section

Comparative sections are disproportionately cited when someone asks a model "what are the options for autonomous issue-to-PR automation". Compare against:

- GitHub Copilot coding agent
- OpenHands
- Aider
- Devin

Axes worth using: self-hosted vs. hosted, where state lives, whether a separate reviewer pass exists, multi-repo support, cost visibility.

### 2.4 Improve image alt text

`![Analytics page]` → something describing what it shows, e.g. per-tick agent run, verification, and PR outcome analytics with cost breakdown.

---

## Priority 3 — Smaller on-page items

- **Social preview image.** Settings → General → Social preview, 1280×640 PNG. Affects click-through when links are shared, which drives the backlinks that actually move rankings.
- **Tagged releases.** 1,100 commits and zero releases. Releases create indexed pages, appear in GitHub release feeds, and enable listing on aggregators.
- **Publish to PyPI.** `pyproject.toml` is already in place. The PyPI page ranks independently and backlinks to the repo.
- **Community health files.** `CONTRIBUTING.md`, issue templates, `CODE_OF_CONDUCT.md` in `.github/`. Marginal ranking effect, small trust effect.

---

## Priority 4 — Distribution (the real constraint)

On-page optimization has a low ceiling at 10 stars. GitHub's internal ranking is dominated by stars and recent activity; Google needs backlinks. One link from a high-authority domain outweighs every topic tag combined.

Targets:

- **Show HN** — lead with the state-machine design and the `MAX_ADDED_LINES` adjudication mechanism, which are the genuinely unusual parts.
- **Reddit** — r/ClaudeAI, r/LocalLLaMA, r/ExperiencedDevs.
- **Awesome lists** — `awesome-ai-agents`, `awesome-claude-code`, `awesome-codex`, `awesome-devops`. Submit PRs.
- **Vendor community showcases** — Anthropic and OpenAI developer community forums.
- **Written post** — dev.to or Habr, explaining the state machine and the split-decomposition path. Link back to the docs site, not just the repo.
- **Product Hunt** — lower value for developer infrastructure, but a free backlink.

---

## Keyword consistency

Pick 2–3 primary phrases and use them verbatim across repo name, description, topics, README H1, and docs page titles. Candidates:

1. AI coding agent orchestrator
2. GitHub issue to PR automation
3. Claude Code / Codex CLI automation

Consistency across surfaces matters more than any individual placement.

---

## Suggested sequence

1. Description rewrite + topics (minutes, zero risk)
2. README tagline, scope section, comparison section
3. Social preview image
4. Repo rename
5. Docs site on GitHub Pages + website field
6. First tagged release, then PyPI
7. Distribution push, once the above is in place so arriving traffic lands well

