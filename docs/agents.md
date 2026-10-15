# Agents

Three analysts (the Relationship Analyst is the RM's view of one client; it does not infer other persons), each a Deep Agents graph (LangGraph underneath) with a narrow tool allow-list:

```
Relationship Analyst  --task-->  Portfolio Analyst  --task-->  Instrument Analyst
 client, concentration,           composition, mandate bands,     reference data, price path,
 liquidity, credit, notes         P&L, change                     events, market context
```

Code: `rm_dashboard.agents` (`analyst.py` builds, runs and assembles; `stubplans.py` scripts the test model).

## How a run works

1. `analyse(role, subject, scope, models)` takes a subject and the run's `as_of`. The date is part of the
   run (`RunContext.as_of`); the model never sees a date parameter and cannot choose one.
2. Entitlement checkpoint, then a check that data exists at `as_of`. If not, a report with status
   `insufficient_data` is returned and no model is called.
3. The agent is compiled with: the allow-listed tools (one LangChain tool per `ToolSpec`, routed through
   `Toolbox.call` so policy, audit and the evidence store apply), `AllowListMiddleware` (the model sees only the
   allow-list plus `task`; Deep Agents' filesystem, planning and general-purpose tools are never shown or
   executed), `PrivacyMiddleware` (every model call passes the PII checkpoint and the pseudonymiser, tool
   results included), and one `CompiledSubAgent` per delegate that runs the child analyst through the same pipeline.
4. The model's final answer is JSON: a summary and findings (`claim`, `confidence`, `evidence_ids`).
5. Deterministic code takes over: the **output guard** drops any finding that cites evidence not produced in this
   run or contains a number absent from the cited results (tolerance: 0.5% relative or the displayed rounding;
   ids, dates and pseudonyms are ignored; `%`, `m`, `bn`, `k` and thousands separators are normalised); gaps
   are collected (tool errors, denials, guard removals, `no_data` results); flags come from cited evidence;
   status derives from gaps (`complete`, `partial`; `insufficient_data` when core data is absent); report
   assembly checkpoints run; pseudonyms are restored last.
6. Whatever goes wrong inside (tool exception, policy denial, model failure, unparsable output), a `Report` is returned
   with the failure as a gap.

## Models

`build_model(settings)` returns `ChatOpenAI` for any OpenAI-compatible gateway (`RM_GATEWAY_URL`,
`RM_GATEWAY_API_KEY`, `RM_MODEL_NAME`). `RM_MODEL_NAME=stub` selects `StubChatModel`, a deterministic scripted
model with failure modes (`uncited_number`, `raise`) used by the tests and the default batch run. Agent logic names no provider.

## Interactive use

`AnalystSession(role, subject, scope, models)`: `start()` runs the standard analysis, `ask(question)` follows up.
Messages persist per `thread_id` (LangGraph `InMemorySaver`; a durable checkpointer can replace it), the evidence store
persists with the scope, and `as_of` stays fixed until `set_as_of(date)`.

## Add an analyst

1. Write a prompt in `agents/prompts.py` (start from `COMMON_RULES`).
2. Add its tool names to `tools/allowlists.py` (names must exist in the registry).
3. Register an `AnalystSpec` in `ANALYSTS` (subject pattern, delegates) and an agent card (`a2a/cards.py`, `SKILLS`).
4. Add a plan to `stubplans.py` for tests (optional for real models).

No other code changes: tools, policy and the guard apply automatically.
