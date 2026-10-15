# architecture-documentation Specification

## Purpose

Keeps one document that shows how the agents are set up, depend on each other, are called and talk to other agents, so that the system can be understood and changed without reading all code, and checks it against the code.

## Requirements

### Requirement: Overview first, then a section per agent
`docs/architecture.md` SHALL open with a high-level overview that classifies every agent by how it is set up and shows how they fit together, and SHALL then contain one section per agent with the same fields: purpose, setup, subject and trigger, inputs and tools, delegation and callers, output and file, checks applied after the model, and model used.

#### Scenario: Overview classifies setups
- **WHEN** a reader reads the overview
- **THEN** each agent is classified as a Deep Agents graph with tool loop, a single model call with code around it, deterministic code with no model, or a mock

#### Scenario: Section per agent
- **WHEN** the registered analysts and stage roles are compared with the document headings
- **THEN** each has its own section containing every field

#### Scenario: Setup is stated, not implied
- **WHEN** an agent is a mock or runs on the scripted `stub` model
- **THEN** its section says so and says what it returns

### Requirement: Runners that call the agents
The document SHALL describe each runner (command, function, agent and model role called, subject and parallelism, arguments, files read and written, failure behaviour), and each agent section SHALL name the runner that calls it or state that it is called only through sessions or the agent-to-agent server.

#### Scenario: Runner per agent
- **WHEN** an agent is run by a batch command
- **THEN** its section names that command and the runner section describes it

#### Scenario: Not run by a runner
- **WHEN** an agent has no runner (the Instrument Analyst, the analyst A2A servers)
- **THEN** its section says it is reached only through interactive sessions or the protocol

#### Scenario: Every command listed
- **WHEN** the console scripts of the project are compared with the runner section
- **THEN** each script appears in it

### Requirement: Agent landscape diagram
`docs/architecture.md` SHALL contain a Mermaid diagram of every agent and batch stage, their dependencies, and what each reads and writes, distinguishing in-process delegation, persisted files between stages and agent-to-agent calls.

#### Scenario: Every agent shown
- **WHEN** the diagram is compared with the registered analysts and stage roles
- **THEN** each role appears in it

#### Scenario: Call paths distinguished
- **WHEN** a reader looks at the diagram
- **THEN** the Relationship Analyst's delegation to the Portfolio Analyst, the batch order of the stages and the KYC peer call are visibly different kinds of edge, with a legend

### Requirement: Calling and running
The document SHALL describe how agents are invoked: the batch runners and their order, interactive sessions, delegation, and the agent-to-agent server, and SHALL include a sequence diagram of one analysis run showing policy checkpoints, tool calls, the evidence store and the output guard.

#### Scenario: Run order
- **WHEN** a reader looks for the order of the batch stages
- **THEN** the document gives the pipeline order with the command of each stage

#### Scenario: One run
- **WHEN** a reader follows the sequence diagram
- **THEN** it shows where the model is called, where tools are called, and where claims are dropped by the guard

### Requirement: Tool matrix
The document SHALL list every registered tool with its kind and purpose and show, for each agent role, whether it is allowed to call it.

#### Scenario: Registered tool missing from the document
- **WHEN** a tool is registered and not in the matrix
- **THEN** the documentation test fails naming the tool

#### Scenario: Allow-list entry
- **WHEN** a tool is on an agent's allow-list
- **THEN** the matrix marks it for that agent, and a tool not on the list is not marked

### Requirement: Agent-to-agent inventory
The document SHALL list the agent cards and skills the analysts publish, the inbound path (peer to analyst) and the outbound path (analyst to peer), the policy checkpoints and delegation chain applied to each call, and SHALL state which parts are mock or not started by any runner.

#### Scenario: KYC peer
- **WHEN** a reader looks up the KYC status tool
- **THEN** the document states that the peer is the in-process mock, that its answer is flagged as mock, and which agent may call it

#### Scenario: Server not started
- **WHEN** no runner starts the analyst A2A servers
- **THEN** the document says the servers exist and are exercised by tests only

### Requirement: Kept in step with the code
The repository's tests SHALL fail when an agent role, a runner command, a registered tool, an allow-list entry or an agent-card skill is absent from `docs/architecture.md`.

#### Scenario: New analyst
- **WHEN** an analyst is added to the registry without being documented
- **THEN** the documentation test fails

### Requirement: Reachable from existing docs
The README and `docs/agents.md` SHALL link to `docs/architecture.md`.

#### Scenario: Link present
- **WHEN** the README is read
- **THEN** it links to the architecture document
