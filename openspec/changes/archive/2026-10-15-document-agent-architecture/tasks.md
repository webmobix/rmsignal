# Tasks

## 1. Gather the facts from the code

- [x] 1.1 Produce the working lists the document is built from — analysts and stage roles, `ALLOWLISTS`, `ToolRegistry.names()` with kind and description, agent-card skills, A2A wiring in `runners/wiring.py` — by a short script or REPL session; verify each list against the code and note any role or tool that does not match the descriptions in `docs/agents.md`

## 2. Write the document

- [x] 2.0 Create `docs/architecture.md` with the overview: a classification table of every agent by setup kind (Deep Agents graph, single call with code, deterministic, mock), model-backed or not, trigger and output; verify each classification against the code (`create_deep_agent` in `build_agent`, `model.invoke` in the reconciler, actions and summary, the mock executor) and that every role from task 1.1 has a row

- [x] 2.1 Create `docs/architecture.md` with the landscape flowchart (stages, analysts, tool kinds, stores, peers; solid, dashed and dotted edges with a legend); verify every role from task 1.1 is a node and the diagram renders in a Mermaid viewer without errors
- [x] 2.2 Add the pipeline-order flowchart with the command of each stage and the files each reads and writes; verify the order and commands equal the README and the runner scripts in `pyproject.toml`
- [x] 2.3 Add the sequence diagram of one analysis run (runner, policy checkpoints, model, tools, evidence store, output guard, report) and a short "how an agent is called" section covering batch runners, delegation, interactive sessions and the A2A server; verify against `agents/analyst.py` and `docs/agents.md` that each step exists
- [x] 2.0a Add the runner section: a table of every console script with function, agent and model role, subject and parallelism, files read and written, plus the shared runner behaviour (registry wiring, model factory, worker pool, failure into gaps, summary and audit files), and put the runners into the landscape and pipeline diagrams; verify the commands against `[project.scripts]` and the behaviour against `runners/batch.py`, `reconcile.py`, `actions.py`, `overview.py` and `outlook.py`
- [x] 2.3a Add one section per agent in the fixed template, each with a "Called by" line naming its runner or stating it is reached only through sessions or A2A (purpose, setup, subject and trigger, inputs and tools, delegation and callers, output and file, post-model checks, model used) for the Relationship, Portfolio and Instrument analysts, Note Reconciler, Client Actions, RM Overview, Market Outlook and Instrument Outlook analysts and the mock KYC peer, with the two small per-agent diagrams; verify each field against the module of that agent and that no section omits a field
- [x] 2.4 Add the tool matrix (kind, purpose, one column per agent role); verify by reading each allow-list that every mark is correct
- [x] 2.5 Add the A2A inventory: published cards and skills, the inbound and outbound sequence diagram with policy checkpoints and delegation chain, and a status column (KYC peer: wired, mock, flagged; analyst servers: server only, exercised by tests); verify the statements against `a2a/`, `runners/wiring.py` and `tests/test_a2a.py`
- [x] 2.6 Add a short "Models" note (which roles use the configured model, that `stub` applies to all of them, that the KYC peer does not depend on it); verify against `agents/gateway.py`

## 3. Keep it in step

- [x] 3.1 Add the sync test to `tests/test_docs.py` (tool set equals the registry, marks equal allow-list membership, every role and card skill present, one heading per role with the eight template fields, every console script in `pyproject.toml` present in the runner section, diagram blocks open with a known keyword); verify it passes now and fails when a tool row is removed from the document
- [x] 3.2 Link the document from the README module table and from `docs/agents.md`, and link back to `docs/agents.md`, `docs/methods.md` and `docs/policy-checkpoints.md`; verify with a test or grep that all links resolve to existing files

## 4. Integration

- [ ] 4.1 Run the Python test suite; verify all tests pass, including the new documentation test
