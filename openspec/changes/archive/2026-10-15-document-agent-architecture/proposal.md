# Proposal

## Why

How the agents fit together is only described in pieces: `docs/agents.md` covers each stage in prose, `docs/methods.md` lists tools, and `docs/policy-checkpoints.md` the policy layer. Nothing shows the whole: which agent exists, who calls whom (in-process delegation, persisted files between batch stages, or the agent-to-agent protocol), which tools each agent may use, and which A2A paths are real versus mock. A reader cannot answer "can the Portfolio Analyst read the market outlook?" or "is the KYC answer real?" without reading the code.

## What Changes

- Add `docs/architecture.md`, the single reference for the agent landscape. It starts with a **high-level overview** (what kinds of agent there are and how they fit) and then **breaks down into one section per agent**, with Mermaid diagrams for:
  - **Setup and dependencies:** every agent (relationship, portfolio, instrument, note reconciler, client actions, overview summary, outlook market and instrument analysts) and the batch stages that run them, with what each stage reads and writes.
  - **How they are called:** the batch pipeline order, in-process delegation (relationship → portfolio via the `task` tool), interactive sessions, and the A2A server path.
  - **A2A communication:** inbound (analyst agent cards and servers) and outbound (the KYC peer), with the policy checkpoints and delegation chain on each call, and which parts are mock or unused by the runners.
  - **One analysis run:** policy, tool call, evidence store, output guard.
- Add a **section per agent** in the same shape: purpose, how it is set up (Deep Agents graph with tool loop, single model call with code around it, deterministic code with no model, or mock), subject and trigger, inputs and tools, what it delegates to or is called by, output contract and file, what the code checks after the model, and which model it uses (configured or `stub`). Each section also names the **runner** that calls the agent. Agents covered: Relationship, Portfolio and Instrument analysts, Note Reconciler, Client Actions, RM Overview (deterministic build plus a summary call), Market Outlook and Instrument Outlook analysts, and the mock KYC peer. A short table at the top classifies them by setup.
- Add a **runner section** (after the overview, before the agents): for each CLI (`rm-dashboard-outlook`, `-analyse`, `-reconcile`, `-actions`, `-overview`, plus `-seed` and `-serve` as the non-agent entry points) the function it runs, the agent(s) and model role it calls, subject and parallelism (per client, per RM, per instrument or market; `max_concurrency` worker pool), arguments, what it reads and writes, and its failure behaviour (always delivered, gaps instead of errors). The runners appear as nodes in the landscape and pipeline diagrams, between the CLI and the agents they call.
- Add the **tool matrix**: every registered tool with its kind (domain, analytics, outlook, peer), purpose and which agents are allowed to call it, taken from the allow-lists.
- Add the **A2A inventory**: agent cards and skills, the mock KYC peer, what is and is not wired to a runner today.
- Add tests that keep the document in step with the code: every agent role, every tool and every allow-list entry appears in the matrix, and the A2A inventory matches the cards.
- Link the document from the README and `docs/agents.md`.
- Documentation only: no runtime behaviour changes.

## Capabilities

### New Capabilities

- `architecture-documentation`: the architecture document exists, covers agents, call paths, tools and A2A with diagrams, and is checked against the code.

### Modified Capabilities

None.

## Impact

- Files: new `docs/architecture.md`; edits to `README.md` and `docs/agents.md` (links); new test in `tests/test_docs.py`.
- Code and APIs: none.
- Related pending changes (`add-mandate-reconciliation`, `add-portfolio-call-sheet`) add a stage, a tool and a view; their tasks keep this document current, and the sync test fails if a new tool or agent is not documented.
- Out of scope: changing how agents are wired, replacing the mock KYC peer, diagrams for the dashboard UI or the read API.
