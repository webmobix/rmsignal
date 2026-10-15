# Design

## Context

Facts established from the code, to be written into the document:
- Analysts are `AnalystSpec`s in `agents/analyst.py` (`ANALYSTS`: relationship, portfolio, instrument). The Relationship Analyst delegates each portfolio to the Portfolio Analyst through the Deep Agents `task` tool, in-process; the Portfolio Analyst no longer delegates to the Instrument Analyst but reads persisted outlooks. Other model-backed roles run as batch stages outside `ANALYSTS`: `note_reconciler`, `client_actions`, `rm_overview_summary`, `outlook_analyst` and the per-instrument outlook role (`outlook_instrument` in `ALLOWLISTS`).
- Runners (`runners/`) are the only callers of the batch agents: `analyse.py` → `batch.run_batch` (Relationship Analyst per client, thread pool of `max_concurrency`), `reconcile.py` → `run_reconcile` (Note Reconciler per client), `actions.py` → `run_actions` (Client Actions per client), `overview.py` → `run_overview` (RM overview per RM), `outlook.py` → `run_outlook` (one market outlook, then one instrument outlook per held instrument, pooled). All build their tools through `wiring.open_registry` (database, point-in-time repository, mock KYC peer) and the model through `build_model`. `seed` and `serve` are console scripts without agents. Commands come from `[project.scripts]` in `pyproject.toml`.
- Allow-lists live in `tools/allowlists.py` (`ALLOWLISTS`); tools are registered by kind in `tools/*_tools.py` (domain, analytics, outlook, peer) and listed by `ToolRegistry.names()`. `docs/methods.md` already lists every tool and is tested for it.
- The batch pipeline is outlook → analyse → reconcile → actions → overview, each stage reading the previous stage's files under `reports/<as-of>/`.
- A2A (`a2a/`): `cards.py` publishes one card per analyst with a skill and a required-input extension; `server.py` (`create_analyst_app`, `AnalystExecutor`) answers tasks with the report contract and carries the requester chain; `client.py` (`PeerClient`) calls peers; `mock_peer.py` is the mock KYC peer. `runners/wiring.py` always wires the KYC peer as the in-process mock; no runner starts the analyst servers (only `tests/test_a2a.py` and `a2a/__init__.py` reference `create_analyst_app`).
- Policy checkpoints `a2a_inbound`, `a2a_outbound` apply to each protocol call (`RunContext.a2a`); the audit log records the delegation chain.
- Setups differ and the document must say which is which, from the code: the Relationship, Portfolio and Instrument analysts and the two outlook roles are built by `build_agent` with `create_deep_agent` (tool loop, `AllowListMiddleware`, `PrivacyMiddleware`, optional `CompiledSubAgent` delegates, LangGraph checkpointer for sessions); the Note Reconciler and Client Actions make one `model.invoke` with the facts in the prompt and everything else in code (the reconciler reads notes through the toolbox in code, not through the model); the RM overview is built deterministically (`overview/build.py`) with one optional summary `model.invoke`; the KYC peer is a scripted `AgentExecutor` that answers the same text for every client; `StubChatModel` replaces the model for all model-backed roles when `RM_MODEL_NAME=stub`.
- `RM_MODEL_NAME=stub` selects the scripted model; anything else is a gateway model. This applies to every model-backed role, not to the peer.

## Goals / Non-Goals

**Goals:**
- One document a new developer can read to place any agent, tool or A2A path.
- Diagrams that show different kinds of dependency differently.
- Tables that cannot silently drift from the code.

**Non-Goals:**
- No change to wiring, the mock peer or the A2A servers.
- No generated documentation site; no diagram rendering toolchain.
- No duplication of the per-stage detail in `docs/agents.md`, which the new document links to.

## Decisions

**One new file, `docs/architecture.md`, with Mermaid in fenced blocks.** GitHub and most editors render Mermaid, and the diagrams stay text under version control. Alternative: extend `docs/agents.md`; rejected because that file is already 260 lines of stage prose and the landscape needs its own entry point. It links both ways.

**Structure: overview, runners, then one section per agent in a fixed template.** The runner section sits between the overview and the agents because a reader follows the call from the command: runner → agent → tools. It uses a table (command, function, agent/role, subject and parallelism, reads, writes) and one shared description of what every runner does the same way (registry wiring, model factory, worker pool, per-subject try/except into a gap, `summary.json` and `audit.jsonl`). Each agent section then has a "Called by" line naming its runner. Console scripts are read from `pyproject.toml` by the sync test, so a new runner cannot be left out. The overview has a classification table (agent, setup kind, model-backed or not, trigger, output) and the landscape diagram. Each agent section uses the same eight fields as the spec (purpose, setup, subject and trigger, inputs and tools, delegation and callers, output and file, post-model checks, model used) and a small per-agent diagram where the shape is not obvious (the Relationship Analyst's delegation and tool loop, the Outlook analyst's carry-forward branch). Alternative: group by setup kind; rejected, because readers look up an agent by name and the classification table already groups them.

**Diagram set.** (1) A landscape `flowchart` with subgraphs for batch stages, analysts, tool kinds, stores and external peers; edge styles: solid for in-process delegation, dashed for files between stages, dotted for A2A, with a legend. (2) A `flowchart` of the pipeline order with commands. (3) A `sequenceDiagram` of one analysis run (runner, policy, model, tools, evidence store, guard, report). (4) A `sequenceDiagram` for the two A2A directions with the policy checkpoints and delegation chain. Beyond these four, per-agent diagrams are limited to those two cases and link to `docs/agents.md` for stage rules.

**Tool matrix as a Markdown table** with one row per registered tool, columns for kind and purpose, and one column per agent role holding a mark where the allow-list contains the tool. Written by hand and verified by a test, not generated. Alternative: generate the table from `ALLOWLISTS` at build time; rejected as it adds a build step to a project that has none, and the explanatory column is prose anyway. A test makes drift visible instead.

**Sync test in `tests/test_docs.py`**, next to the existing methods test: parse the matrix rows, assert the set of tool names equals `ToolRegistry.names()`, that each mark equals membership in `ALLOWLISTS[role]`, that every role in `ANALYSTS` and `ALLOWLISTS` appears, and that every card skill id in `a2a.cards.SKILLS` appears in the A2A inventory. Mermaid syntax itself is not parsed; a short check asserts each diagram block opens with a known diagram keyword.

**State what is mock and what is unused.** The A2A inventory has a "status" column: `wired` (KYC outbound, mock), `server only, tests` (analyst servers). This is the part readers most often get wrong.

**Keep current through the pending changes.** The tasks of `add-mandate-reconciliation` and `add-portfolio-call-sheet` are not edited here; the sync test failing on an undocumented tool or role is the mechanism. The document is written for the code as it stands when this change is applied.

## Risks / Trade-offs

- [Hand-written matrix drifts] → the test fails on any tool, role or mark mismatch; prose columns can still go stale, which the review catches.
- [Mermaid renders differently across viewers] → keep to `flowchart` and `sequenceDiagram`, no styling beyond line style and a legend.
- [Sections duplicate `docs/agents.md`] → the new document states relationships and links to stage detail instead of restating rules.
- [Pending changes alter the picture] → documented above; the sync test covers tools and roles, not edges.
