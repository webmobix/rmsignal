# llm-call-logging Specification

## Purpose

Makes every LLM call observable: who made it, how long it took and how many tokens it used, per call and per runner run, without logging any prompt or response content.

## Requirements

### Requirement: One log record per LLM call
Every LLM call made by an agent in any runner or interactive session SHALL produce exactly one log record when the call ends, carrying the run id, thread id, agent, runner, duration in milliseconds, input tokens, output tokens, total tokens and an outcome of `ok` or `error`. A call in a delegated (child) agent SHALL carry the same run id as its parent and its own agent name.

#### Scenario: Successful call
- **WHEN** the Relationship Analyst makes a model call during `rm-dashboard-analyse`
- **THEN** one record is logged with that client's run id, thread id, agent `relationship_analyst`, runner `analyse`, the duration, the token counts and outcome `ok`

#### Scenario: Delegated call
- **WHEN** the Portfolio Analyst makes a model call on behalf of the Relationship Analyst
- **THEN** its record has the parent's run id and agent `portfolio_analyst`

#### Scenario: Failed call
- **WHEN** a model call raises an error
- **THEN** one record with outcome `error`, the error type and the duration is logged, and the run continues exactly as it did before this change

### Requirement: Thread identity groups a graph run
Every top-level agent graph run (or interactive conversation) SHALL have one thread id, and every LLM call made anywhere under it SHALL carry that thread id: calls of the top-level agent, of delegated sub-agents, and of any model call triggered from within its tool calls. Separate graph runs (for example two clients in a batch) SHALL have different thread ids. Filtering a log by thread id SHALL return all calls of that run and no others.

#### Scenario: Sub-agent grouped with its parent
- **WHEN** the Relationship Analyst delegates a portfolio to the Portfolio Analyst
- **THEN** the records of both agents carry the same thread id and different agent names

#### Scenario: Model call inside a tool call
- **WHEN** a tool executed by an agent causes a further model call
- **THEN** that record carries the agent's thread id

#### Scenario: Parallel clients
- **WHEN** a batch analyses two clients concurrently
- **THEN** the records of each client share one thread id and the two clients' thread ids differ

#### Scenario: Interactive session
- **WHEN** several turns are asked in one session with thread `thread_ab12`
- **THEN** every record of every turn carries `thread_ab12`

### Requirement: Missing token usage is explicit
When a model provider does not report token usage, the record SHALL show the token fields as unknown rather than zero, and the run summary SHALL count such calls separately.

#### Scenario: No usage reported
- **WHEN** a call completes and the provider returned no usage
- **THEN** the record shows input, output and total tokens as `n/a` and the summary's `calls_without_usage` is incremented

### Requirement: Run summary at the end of a runner
When a runner finishes, it SHALL log a summary with elapsed wall time, number of calls, number of failed calls, input, output and total tokens, the same figures per agent, the slowest call, and the number of calls without usage. The runner's `summary.json` SHALL also carry an `llm` object with the call counts and token totals (no durations, so that a rerun on identical inputs stays byte-identical). The summary SHALL be produced even if some or all clients failed, and also when no model call was made.

#### Scenario: Summary after a batch
- **WHEN** `rm-dashboard-analyse` completes for 10 clients
- **THEN** the console and log file end with one summary and `summary.json` has an `llm` object with the same call and token totals

#### Scenario: No model calls
- **WHEN** a runner finishes without any model call (for example an unchanged outlook)
- **THEN** the summary reports zero calls and zero tokens on the console, and an existing `run.log` and `summary.json` are left unchanged

#### Scenario: Concurrent clients
- **WHEN** clients are processed in parallel
- **THEN** the summary totals equal the sum of the individual records and no record is lost or interleaved within a line

### Requirement: Console and file output
Records and the summary SHALL be written to the console (standard error) and to `run.log` in the runner's output folder. The level SHALL be configurable through `RM_LOG_LEVEL` (default `INFO`). A runner that makes at least one call SHALL start a fresh `run.log`; one that makes none SHALL leave an existing one untouched.

#### Scenario: Both sinks
- **WHEN** a runner makes model calls
- **THEN** the same records appear on standard error and in `run.log`

#### Scenario: Level raised
- **WHEN** `RM_LOG_LEVEL=WARNING` is set
- **THEN** successful call records are not written, failed calls and the summary's warnings are

### Requirement: No content in logs
Log records and the summary SHALL NOT contain prompts, responses, tool arguments or personal data. Subject identifiers (client, portfolio or instrument ids) are allowed.

#### Scenario: Content check
- **WHEN** a run with known client names in its prompts completes
- **THEN** no client name or message text appears in the console output or `run.log`

### Requirement: Logging is provider-independent
The one-record-per-call log SHALL be produced for every supported model provider, including Gemini on Vertex AI, with the same fields. Token counts SHALL be taken from the provider's reported usage; when a provider reports none, the counts SHALL be absent and the call SHALL be counted as without usage, as for any other model.

#### Scenario: Vertex Gemini call
- **WHEN** an agent makes a model call through the `vertex` provider
- **THEN** one record is logged with run id, thread id, agent, runner, duration, token counts and outcome `ok`

#### Scenario: Vertex call fails
- **WHEN** a Vertex call raises an error such as permission denied
- **THEN** one record with outcome `error` and the error type is logged, and the run continues as for any failed call
