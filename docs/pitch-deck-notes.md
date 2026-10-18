# RMSignal: pitch deck content

Plain-English text for the slides. Each section is one slide, or two at most. Short lines are meant to be pasted straight onto slides.

---

## 1. The problem

**Relationship Managers (RMs) have data, not direction.**

- Priscilla Ong looks after 20 clients and USD 596m in assets.
- Today's tools show valuations, charts and allocations. They describe. They do not advise.
- She has to work out the risks herself: Who is breaching a mandate? Who needs cash soon? Whose loan is close to its limit? Whose KYC review is overdue?
- Some risks hide. A client with three portfolios can look fine in each one and be badly concentrated across all three.
- Her own notes sometimes say the opposite of what the numbers show.

**The question she needs answered: "What should I know, and what should I do next?"**

---

## 2. What RMSignal is

**An intelligence layer between the portfolio data and the Relationship Manager.**

- It reads the portfolios, the market events, the mandates and the RM's own notes.
- It gives the RM a ranked list of next actions: who to call, what to say, and why.
- Every action links to the proof behind it.
- The RM stays in charge. The system suggests. The RM decides.

---

## 3. What the RM sees (the screens)

| Screen | What it answers |
|---|---|
| **Overview** | Who do I call first? All actions across all clients, ranked by importance and timing. A short written summary on top. |
| **Actions** | The full action list. Filter by importance (high, medium, low). |
| **Clients** | One page per client: all portfolios together, allocation, currencies, biggest positions, what structured products really hold underneath, liquidity against planned spending, credit headroom. |
| **Compare snapshots** | What changed between two of the five dated snapshots, shown next to the events that happened in between. |
| **Scenarios** | What happens to this client if the Gulf situation calms down, gets worse, or rates stay high. |
| **Instruments** | The bank's view on each instrument. |
| **Market** | The bank's market view and the events that drive it. |
| **Evidence drawer** | Click any claim to see the data, the calculation, or the note behind it. |

---

## 4. How an insight reaches the RM

```
Market events + client data + RM notes
        ↓
1. Write the bank's market view and instrument views
        ↓
2. Study each client and portfolio
        ↓
3. Check the RM's notes against the numbers
        ↓
4. Check mandate breaches against the notes
        ↓
5. Turn findings into actions (what, why, how important, how soon)
        ↓
6. Rank all actions across the RM's book
        ↓
RM reviews, decides, calls the client
```

Each step saves its result in a file. Each step reads the file before it. Nothing is hidden.

---

## 5. What each agent does

Think of a small team. Each member has one job and can only use the tools for that job.

| Agent | Its job, in one line |
|---|---|
| **Market Outlook agent** | Writes the bank's view of the market (equities, rates, currencies, commodities, volatility). Every view cites the events behind it. Changes only when there is new data. |
| **Instrument Outlook agent** | Writes the bank's view on each instrument held by clients, compared with its peers. Written once, shared by all clients. |
| **Relationship Analyst** | Looks at one client the way the RM does: profile, KYC, risk across all portfolios, cash needs, credit, notes. |
| **Portfolio Analyst** | Looks inside each portfolio: what is held, mandate limits, performance, what changed. Works for the Relationship Analyst. |
| **Note Reconciler** | Reads the RM's notes and checks each against the facts. Result: consistent, contradicted, or cannot be verified. |
| **Mandate Reconciler** | Takes the mandate breaches that code found and checks what the notes say about each. Result: no note, acknowledged, client-directed, or contradicted. A claimed waiver is shown as a claim and never hides a breach. |
| **Client Actions agent** | Turns the findings into a short list of actions: what to do, why, how important, how soon. |
| **RM Overview** | Mostly plain code. Ranks all actions across all clients and groups them. One optional AI call writes the short summary. |
| **Scenario agent** | Estimates how each market channel moves in a scenario (best, likely, worst). Code then works out the effect on each portfolio. |
| **KYC peer** | A mock in this MVP. It stands in for the bank's real KYC system to show how agents can talk to each other. |

---

## 6. Why you can trust it

This is the most important slide for a bank.

1. **AI never does the maths.** Code calculates every number: weights, concentration, loan-to-value, liquidity, mandate drift, performance.
2. **Every claim cites evidence.** A finding must point to the data it came from.
3. **A code check removes bad claims.** If a number in a claim is not in the cited evidence, the claim is deleted and listed as a gap.
4. **The model proposes. Code decides.** Importance levels have fixed floors. For example, an overdue KYC review is always critical. The AI can raise a rating but never lower it below the floor.
5. **Facts come from one source.** For anything that happened in 2026, the event log is the only source. The model's memory is not used.
6. **No look-ahead.** Every run is tied to one date. The model cannot pick a date or see later data. The same date gives the same result.
7. **Honest about gaps.** The reports say "partial" and list what could not be checked. The data has no related persons or beneficial owners, so the report says so instead of guessing.
8. **Privacy by design.** Client names are replaced with codes before anything reaches the model, and put back afterwards. Every model call is logged by size and time, never by content.
9. **Audit trail.** Every tool call and policy check is written to a log.
10. **Human in the loop.** The RM can inspect, reject, or change anything. Notes are never overwritten.

---

## 7. Real examples from the demo data

Use two or three of these. Go deep, not wide.

- **Cheung Kwok Wing (CL-0012).** Holds long-dated bonds at a loss. The bank's view on rates is negative. The action: discuss holding at a loss before he keeps waiting for recovery.
- **Alistair Pemberton-Hale (CL-0007).** Commodities are above the Balanced mandate ceiling. A waiver is on file. The system shows the breach and the waiver as a claim. The RM decides.
- **Tan Boon Huat (CL-0011).** Succession discussed again and again, but no trust or holding structure exists. The action: progress succession and estate planning.

Book-level numbers from the demo run (26 Aug 2026): 20 clients, USD 596.2m in assets, 93 next actions, 40 high, 46 medium, 7 low.

---

## 8. Scenarios: what could happen next

- Three scenarios, each tied to a real event in the event log: **Gulf de-escalation**, **Gulf deterioration**, **Rates higher for longer**.
- For each client and each portfolio: best, likely and worst effect in USD over three months.
- Code does the maths. The AI gives judgement and wording.
- On screen it says: these are cases, not probabilities.

---

## 9. What makes it different

- **Advice, not description.** Output is a ranked action list, not another chart.
- **Book-wide view.** Who to call first across all clients.
- **Finds hidden risk.** Looks across portfolios and into structured products.
- **Uses the RM's own notes** and tells her when they disagree with the data.
- **Explainable.** One click to the source of any claim.
- **Safe by design.** Code checks the AI, not the other way round.

---

## 10. Fit for a bank (feasibility)

- **Read-only.** The system never changes client data and never trades.
- **Model-agnostic.** Works with any OpenAI-compatible model endpoint. A bank can use a private, in-house model. A test model runs the whole pipeline with no provider.
- **Batch design.** Heavy work runs ahead of time. The dashboard only reads saved results, so it is fast and cheap.
- **Small, separate pieces.** Each agent has a narrow tool list and its own file output. Easy to test, review and replace.
- **Policy hooks.** Ten checkpoints (access, privacy, report release and more) are in place. They are a mock engine in this MVP. A real bank policy engine plugs into the same interface.
- **Agent-to-agent standard.** Agents publish cards and can call each other, such as the KYC peer, using the A2A standard.
- **Tested.** Unit and component tests cover the backend and the interface.

---

## 11. What is real and what is a mock (be upfront)

| Real in the MVP | Mock or limited in the MVP |
|---|---|
| Calculations, guards, ranking, audit log | Policy engine (allows everything, and says so in every report) |
| Market, instrument and client analysis | KYC peer (scripted answers) |
| Notes and mandate reconciliation | News feed (the curated event log only) |
| Scenario maths | Scenario shock sizes come from the AI, with evidence, and are bounded by code |
| Dashboard and evidence drawer | No sign-in (the RM profile is mocked) |

Data problems we noticed: reports are `partial` because the dataset has no related persons or beneficial owners; some private-fund valuations lag by a quarter; some positions carry data-quality flags. We show these. We do not hide them.

---

## 12. Impact

- **For the RM:** less time hunting for risks, more time with clients. A clear reason for every call.
- **For clients:** timely, personal conversations that fit their mandate and goals.
- **For the bank:** fewer missed breaches, better records, and an AI approach that compliance can review.
- **For the RM's role:** the RM is not replaced. RMSignal makes her better prepared.

---

## 13. Next steps

- Connect to the bank's real policy engine and KYC system.
- Add related persons and beneficial owners when the data exists.
- Add an external news feed behind the same tool.
- Add tax-aware ideas and life-event planning.
- Let the RM accept, reject or edit each action, and learn from it.
- Add sign-in and per-RM access.

---

## One-sentence pitch

**RMSignal turns portfolio data into a short, ranked, explained to-do list, so the Relationship Manager knows who to call first, what to say, and why, with the proof one click away.**
