# BaerSignal — product and handoff document

SingHacks 2026, Julius Baer: "From Portfolio Monitoring to Intelligence".

This document is written so someone who has never seen the project can pick it
up. It covers what the product does, how every number is produced, and what was
decided and why.

**Status:** working end to end. All modules built. Section 19 lists what is left.

---

## 1. What it is

BaerSignal is a workbench for one relationship manager, Priscilla Ong, who
covers 20 clients and USD 596m at Julius Baer's Asia desk.

It reads her whole book, finds the problems, ranks the clients by which problem
will hurt first, and turns each problem into a client note she can send.

There are three screens:

| Screen | What it does |
|---|---|
| The book | 20 clients ranked by their worst open problem, plus a calendar of dated obligations |
| Client dossier | Four tabs: To raise, Portfolio, Scenario analysis, Context |
| Composer drawer | The draft client note. Accept, amend or dismiss. Nothing executes. |

Current output: **71 findings across 18 clients.** Two clients have no findings
at all.

Two earlier write-ups exist and are worth reading before changing direction:

| | |
|---|---|
| Game plan | https://claude.ai/code/artifact/d7c26a0c-b95c-4283-b849-64eca1a94c72 |
| Client timeline explorer | https://claude.ai/code/artifact/0acdac25-83ee-4e6a-882d-b3c3a4b82454 |

The direction chosen was **Direction 3, RM Intelligence Workbench**, from the
three building blocks in `README.md`.

| Finding type | Count |
|---|---|
| Mandate (band breaches, position limits, exclusions) | 29 |
| Life event (a dated obligation large enough to matter) | 14 |
| Concentration (one name, seen through wrappers) | 11 |
| Tax (harvestable losses) | 7 |
| Funding (can the promise be paid) | 4 |
| Collateral (loan-to-value against the margin trigger) | 3 |
| Purpose fit (income maturing after it is needed) | 2 |
| Data quality (a stale mark) | 1 |

Clients fall into three tiers: **5 act, 9 review, 6 watch.**

---

## 2. How to run it

```bash
python3 engine/build.py     # reads data/, writes app/findings.json and .js
open app/index.html         # no server, no install, Python standard library only
```

`build.py` prints the ranked book to the terminal, so you can check the engine
without opening the browser.

The one optional step is narration, which calls the Claude API:

```bash
printf '%s' 'sk-ant-...' > ~/.anthropic_key && chmod 600 ~/.anthropic_key
python3.13 -m pip install anthropic
python3.13 engine/narrate.py --limit 3    # test on three findings first
python3.13 engine/narrate.py              # then all of them
python3 engine/build.py                   # fold the drafts into the bundle
```

Without a key the workbench still works. Every draft falls back to a
deterministic template and labels itself as one.

---

## 3. The architecture

The whole product rests on one rule:

> **A language model never computes a number that reaches a client.**

Four layers:

| Layer | What it does | Where |
|---|---|---|
| 1. Finding engine | Reads the CSVs, applies rules, emits typed findings with numbers | `engine/modules/` |
| 2. Triage | Ranks the book. Deterministic. Weights in one visible block. | `engine/triage.py` |
| 3. Narration | Claude explains the finding and drafts the note. Never recomputes. | `engine/narrate.py` |
| 4. Composer | Accept / amend / dismiss. Nothing is executed. | `app/app.js` |

Every number in the interface comes out of `engine/`. `app/app.js` formats and
lays out; it does no arithmetic on the dataset. That is what lets every figure
open up to the rule that made it.

**One sanctioned exception.** `app/triage.js` re-runs Layer 2 in the browser so
the RM can move the ranking weights and watch the book reorder. It reads nothing
from `data/` and derives no new fact — it multiplies severities the engine
published by weights the engine published. `parityCheck` re-runs it at the
engine's own settings on every page load and warns to the console if the two
ever disagree. Severity itself is never computed in the browser.

Two supporting rules:

- Anything the product says about 2026 comes from `data/event_log.csv`, never
  from the model's own memory of the year.
- Direct identifiers (name, account number, nationality, exact age) never leave
  the machine. The *substance* does, including note text, because reading the
  notes is the most valuable thing narration does. The workbench itself sits
  inside the perimeter and shows everything.

---

## 4. What is in the engine

```
engine/
  loader.py        Reads every CSV. Handles FX, custody, look-through, stale marks.
  notes.py         Turns RM free text into structured claims, always with the quote.
  schema.py        The Finding shape every layer agrees on.
  severity.py      The 0-100 scale. Every calibration constant lives here.
  triage.py        Book ranking. WEIGHTS and TIERS live here and nowhere else.
  performance.py   Return on cost, per-position contribution, event attribution.
  upcoming.py      The diary: every dated obligation across the book.
  scenario.py      Module F. Scenario analysis.
  clientnote.py    The deterministic client note, in plain language, six languages.
  narrate.py       Layer 3. Calls Claude, caches, verifies.
  build.py         Runs everything, writes the bundle.
  modules/
    governance.py  Mandate bands, single-position limits, binding exclusions.
    liquidity.py   Collateral headroom, funding feasibility.
    client_fit.py  Purpose fit, look-through concentration, life events, stale marks.
    tax.py         Loss harvesting, gated on tax domicile.
    rebalance.py   Module E. Constrained trade plans.

app/
  index.html   A shell. app.js renders every screen into #view.
  app.js       Rendering. No arithmetic on the dataset.
  triage.js    A port of triage.rank, for the live retune.
  calendar.js  The diary as agenda, month or week. Editable.
  styles.css   The visual system from design.md.
  findings.js  Generated. The only thing the UI reads.
```

---

## 5. How severity is calculated

Severity is **how bad one finding is**, on a 0-100 scale that is comparable
across finding types. It is a property of the finding, so changing it means
re-running the engine.

Every constant that shapes a severity lives in one block at the top of
`engine/severity.py`. No module invents its own. The main ones:

| Constant | Value | Meaning |
|---|---|---|
| `MANDATE_BAND_PER_PP` | 2.2 | Severity points per percentage point outside a mandate band |
| `DISCRETIONARY_X` | 1.4 | Multiplier when the bank chose the position, not the client |
| `DIRECTED_X` | 0.7 | Multiplier when the client asked for it and it is on file |
| `WAIVED_X` | 0.0 | Waived in writing. Governed, never raised. |
| `LIMIT_PER_PP` | 6.0 | Per point over a single-position limit. Steeper, because it is a hard cap. |
| `EXCLUSION_DISCRETIONARY` | 98.0 | A binding exclusion breached inside a mandate the bank runs |
| `LIFE_PER_PCT` | 2.6 | Per % of wealth a dated obligation represents |
| `FIT_PER_PCT` | 2.0 | Per % of wealth maturing after the horizon it funds |
| `CON_RUNGS` | 88 / 74 / 60 / 44 / 20 | By single-name share: 40%+, 30%+, 20%+, 12%+, below |
| `COLLATERAL_RUNGS` | 95 / 75 / 45 / 15 | By headroom to the margin trigger: 2pp, 6pp, 12pp, above |
| `FUNDING_RUNGS` | 85 / 60 / 35 / 12 | By cover ratio: below 1.0x, 1.5x, 3.0x, at or above |

Every severity is assembled through a small builder called `Sev`, which records
each step. The result is that a finding carries its own arithmetic, and the
dossier shows the ladder instead of just asserting a total:

```
34.9% of wealth maturing past a 2038 horizon
  → sleeve share x 2.0        = 69.8
  → +20 for 40 years overshoot = 89.8
  → held at the 88 ceiling     = 88.0
```

**Ceilings are deliberately below 100.** An earlier calibration put nine clients
in the "act" tier, which made the tier meaningless.

Some rules also have a **report threshold** — a severity below which the finding
is not worth the RM's time and is not emitted at all. Funding reports below 3.0x
cover; collateral reports below 40 if it has never breached.

---

## 6. How the book is ranked

Ranking uses two things severity does not: a **weight per finding type**, and
**tier thresholds**. Both are judgement rather than data, so both belong to the
RM and both are adjustable in the browser without a rebuild.

```python
WEIGHTS = {
    "collateral": 1.00, "funding": 1.00, "mandate": 1.00,
    "purpose_fit": 1.00, "concentration": 1.00,
    "life_event": 0.95, "tax": 0.85, "data_quality": 0.75,
}
TIERS = {"act": 90.0, "review": 60.0}   # below "review" is "watch"
MATERIAL = 60.0                          # counts toward the tiebreak
```

The score for a client is:

```
score = peak x 1000 + material_count x 10 + min(wealth / 1e7, 9)
```

**The peak dominates. Count only breaks ties, and wealth only breaks those.**
This was a deliberate correction: an additive score buried CL-0005's compliance
breach at rank 10 because she had fewer other problems than clients whose
problems were individually smaller.

The ranking panel exposes eight weight sliders plus the three thresholds. The
book reorders live behind the open panel, and rows show how far they moved from
the engine's own ranking. Settings are kept in `localStorage`; one button
restores the defaults. The whole severity calibration table is shown in the same
panel, read-only, so the RM can see the constants she cannot move from there.

---

## 7. What each rule looks for

**Mandate** (`governance.py`) — three separate checks. An asset class outside
its band. A single position over the mandate's position cap. An instrument on
the mandate's binding exclusion list. Custody portfolios are excluded from all
three, because the client directs those.

**Collateral** (`liquidity.py`) — loan-to-value against the facility's own
margin trigger, at all five snapshots. Lending value, not market value.

**Funding** (`liquidity.py`) — everything falling due in twelve months against
what can be sold at daily liquidity. Then the harder question: does selling
enough to pay it trip a margin call, because the assets being sold are the
collateral.

**Purpose fit** (`client_fit.py`) — income positions maturing after the horizon
they are meant to fund, and underwater. This is CL-0012: 34.9% of his wealth
matures after his 2038 horizon and is USD 4.9m down.

**Concentration** (`client_fit.py`) — single-name exposure across every
portfolio, seen through structured product wrappers. Adds points when the
largest exposure repeats the source of the client's wealth instead of
diversifying it.

**Life event** (`client_fit.py`) — a dated obligation large relative to wealth.
Weighted up if confirmed, and again if there is a health note in the file.

**One obligation is one problem.** A dated promise produces *two* findings, and
that is correct: the life-event rule says it is large relative to the wealth
behind it, the funding rule says whether the portfolio can meet it. Different
claims, different actions, both worth a card — CL-0014 is told his HKD 60m is
29% of his wealth *and* that selling to pay it trips a margin call.

But it is one obligation, so it counts once. `build.link_duplicates` pairs a
life event with the funding finding whose 12-month window contains the same
`need_id`; the weaker of the pair (by severity, not by dimension — for CL-0007
the life event is the more serious half) records `same_fact_as` and drops out of
the material tiebreak. Chains are resolved to the cluster head, so CL-0006's two
obligations plus one funding verdict contribute one count, at their worst
severity. Both cards stay on screen and each names the other.

Counting it twice is the specific failure that once buried CL-0005's compliance
breach at rank ten. **Fixing it moved CL-0014 from rank 2 to rank 3**, behind
CL-0002: they tie on peak (95) and now on material count (3), and wealth breaks
the tie. That is the correct consequence, and the demo order in `PITCH.md`
accounts for it — CL-0014 is introduced by name, not by rank.

**Tax** (`tax.py`) — harvestable losses, gated on tax domicile. For a Hong Kong,
Singapore or UAE domicile the finding is that there is nothing to harvest,
because those jurisdictions levy no capital gains tax.

**Data quality** (`client_fit.py`) — a mark that has not moved across all five
snapshots. `SYN-AL-0308` is marked 2025-09-30 at every snapshot and is 68% of
CL-0002's wealth.

---

## 8. Module E: how trade plans are made

`engine/modules/rebalance.py`. This is a **constrained suggestion, not an
optimiser.**

An optimiser answers "what is the best portfolio?" That question needs data this
dataset does not have, and no client asked it. This answers the narrow question
an RM actually faces: *the mandate says equity must be under 55% and it is at
67.7% — what would I sell, and what stops me?*

### The four constraints, in the order they bind

| Constraint | Rule |
|---|---|
| Liquidity | Sell only positions with `liquidity_tier = Daily`. A quarterly-dealing fund is not a Monday trade, whatever its market value says. |
| Gated | Not even a Daily fund the RM has recorded as gated. CL-0017's private credit manager has gated three quarters running; the liquidity column does not know that. |
| Protected | Never a position the notes protect. CL-0005's Sunrise Palm holding is a family asset from before the sustainability policy. |
| Collateral | Never take a pledged portfolio past its margin trigger. Selling collateral removes lending value; buying back adds some in. Modelled as one movement. |

Exclusions cut the other way: an instrument on the mandate's own exclusion list
is sold **first**, ahead of everything else.

Minimum trade size is **USD 25,000**. Below that the trade costs more than it
corrects.

### Where the client's risk profile enters

The risk profile is expressed **once**, as the mandate the household signed. The
plan reads that mandate's bands. Conservative caps equity at 30%, Growth at 78%,
so the same breach produces a different trade for each.

The plan does not re-derive risk from `risk_tolerance_score`. Two places to look
up how much equity a client may hold is one place too many.

What the plan does **not** read: horizon, stated liquidity needs, tolerance
score. Each plan card names these as excluded, so nobody has to discover it.
They belong to the conversation, not to the constraint set.

### Output

**28 plans across 11 of 20 clients.** Examples:

- **CL-0005.** Her Global Energy Majors fund exits in full. Her Sunrise Palm
  holding is also on the exclusion list, but the notes protect it, so it is
  blocked *and* escalated: the exclusion is binding, so this goes to compliance
  rather than being dropped.
- **CL-0011.** 11.4m of Alternatives over his band, and the plan raises **zero**
  — all three candidates are quarterly dealing or worse. "This cannot be fixed
  by selling" is itself the finding.

Proceeds are routed to whichever classes sit below their band, into something
already held. Where nothing is held, the plan says the purchase needs an
instrument decision, which is not a rule's to make.

### Why nine clients have no plan

Four reasons, all correct:

1. Nothing is breached. CL-0008 and CL-0010 have no findings at all.
2. The breach is under the USD 25,000 minimum.
3. The finding is not the kind a trade fixes. A concentration finding spanning
   three portfolios through look-through is a conversation, not a sell order.
   CL-0001 and CL-0019 are here.
4. The client waived it in writing. CL-0007's gold is 8.9 points over his
   Balanced ceiling; he instructed the purchase after being told, and there is a
   suitability waiver on file. The plan builder skips waived findings and the
   Raise tab says so.

Protected positions are resolved from the note text. "The Sunrise Palm position
is a family holding" resolves to Sunrise Palm Resources Ltd. "Did not want to
discuss reducing the legacy shareholding" resolves to nothing, and the plan
carries it as an unresolved warning with the quote rather than guessing.

A plan attaches to the finding that motivated it. It never emits a finding of
its own, because a client with one band breach must not rank as though they had
two problems.

---

## 9. Module F: how scenario analysis works

`engine/scenario.py`. The module **reprices a stated shock. It does not forecast
one.** No probability is attached to any scenario, and the interface says "if",
never "will".

### How the four scenarios are formed

They are **written by hand**, in one visible block at the top of `scenario.py` —
the same treatment as `WEIGHTS` and the severity constants. Nothing derives
them. No model proposes them. They are assumptions on the page, put there to be
argued with.

Each scenario is a list of **channel moves**. A channel is a narrow set of
words — `shipping`, `energy`, `gold`, `technology`, `sovereign`, `credit`,
`high yield`, `reit`, `property`, `commodity`, `semiconductor`, and two equity
channels. Each move says which channel, what percentage, and why it is in the
list.

| Scenario | Calibrated against | The moves |
|---|---|---|
| The Strait of Hormuz reopens | 2026-03-04, closure, Brent past USD 120 | shipping −32, energy −18, gold −9, commodity −7, credit +1.5 |
| Long rates rise another 100bp | 2026-06-17 and 06-19, policy repricing | sovereign −8, reit −9, tech −7, property −6, credit −4, high yield −3 |
| The easing timeline comes back | 2026-06-17 and 07-29, reversed | sovereign +7, reit +8, tech +6, DM equity +4, credit +3.5, high yield +3, property +4 |
| A 25% drawdown in technology | 2026-06-05, USD 2tn off megacap tech | tech −25, semis −30, DM equity −8, credit −2 |

**The event log supplies calibration, not the scenario.** The obvious objection
is: if the event already happened, what is the value? Three answers, all of them
stated on the tab:

1. **None of the four has happened to these holdings.** The portfolio that would
   take a Hormuz reopening today is not the portfolio that took the closure in
   March. Six months of drift, purchases and a rate move sit in between.
2. **Three of the four are not replays.** Hormuz *re*opening is the recorded
   event run backwards. Another 100bp is a continuation. The easing timeline
   coming back is that decision reversed. Only the technology drawdown repeats a
   shape the log contains.
3. **What the log gives is the size of a move of that kind when one really
   happened.** So the numbers are argued from evidence rather than invented at a
   desk. A scenario with no provenance is a number somebody made up.

**One of the four is deliberately an upside.** With three adverse shocks, every
client's best case was "nothing much happens", which is a one-sided stress test
rather than a range.

The percentages themselves are a judgement call, anchored on those event rows.
That is the softest part of the module, which is why every scenario carries a
`caveat` field printed on screen rather than buried in a comment.

### How the valuation is done

Four steps, all plain arithmetic on today's holdings.

**1. Match holdings to channels.** For each instrument, build a word set from
its name, asset class, sub-class, sector and region. A channel matches only if
**every** one of its words is present. `{high, yield}` must both appear. This is
narrow on purpose: a channel that matches everything encodes nothing. The
matcher is shared with the event attribution in `performance.py`.

**2. Apply the moves additively.** A shipping company caught by both `shipping`
and `energy` takes both moves, and the breakdown column shows it. Nothing is
netted.

**3. New value.**

```
after = market_value x (1 + total_pct / 100)
```

Summed across positions, that is the client's repriced wealth. There is no
revaluation model, no beta, no correlation matrix, no volatility assumption.

**4. Then the two consequences that matter.**

- *Collateral.* Lending value moves by the same factor, and LTV is recomputed
  against the facility's trigger. This is how CL-0014 gets a margin call from a
  rate move.
- *Mandate bands.* Asset class weights are recomputed and crossings reported
  **in both directions**, because a shock that heals a breach is worth knowing
  too.

A holding no channel reaches does not move, and is **listed as untouched**
rather than silently zeroed.

### Results worth showing

- **CL-0019 asked for this and never got an answer.** He holds 24.3% of his
  wealth in one shipping company plus a shipping fund. A Hormuz reopening
  reaches 38.3% of his wealth: **−7.97%, USD −2.6m.**
- **CL-0014 gets a margin call from a rate move.** Another 100bp takes CF-0002
  from 69.4% to 70.2%, through his 70% trigger. That is a second, unrelated
  route to the same margin call the funding finding already found.
- **CL-0002's worst case is bigger than his whole year.** The technology
  drawdown is **−24.4%**, larger than every move his five measured snapshots
  contain put together.

### What it deliberately does not do

Both stated on screen:

- **No hedges.** The dataset records none, so nothing is netted against one.
- **No duration.** `instruments.csv` carries no maturity for bonds, so every
  sovereign takes the same move. For a 2045 Treasury against a 2028 that is
  simply wrong, and it understates the long end.

And the structural limit: this is one instantaneous reprice, not a path. No
time, no ordering, no second-round effects. The margin call does not trigger
forced selling that moves prices again.

### On the wealth chart

The Portfolio tab draws the widest and the mildest of the four to the right of a
dashed rule at today. It is drawn as an **instantaneous reprice off the last
measured point**, not a curve running through future dates, because a curve
through future dates would be a prediction. There is no path between the two and
none is drawn. Each endpoint clicks through to its scenario.

---

## 10. The deterministic client note

`engine/clientnote.py`. Every finding carries a client-ready note that exists
with no API key, no network and no model — and, for the six clients not reported
to in English, that note exists **in their language too**.

Two problems, and they turned out to be one. The old stand-in pasted the
finding's own `detail` string into a greeting. That string is written for
Priscilla: *"USD 7.7m falls due within twelve months against USD 11.4m sellable
at daily liquidity, of which USD 0.0m sits outside any pledged portfolio"* is
exactly right for an RM and unreadable for the person whose money it is. And an
English paragraph cannot be sent to a client reported to in Traditional Chinese,
so the drawer previously just refused — honest, but not useful.

Both are fixed in the **engine**, because the note contains figures and a figure
in this product comes out of `engine/` or it does not appear. The module holds
fixed sentence frames with slots; the slots are filled from the finding's own
`numbers`. Nothing is computed there that the finding did not already carry, and
nothing is translated at runtime — a sentence a compliance officer cannot read
back in both languages has no business being sent to a client.

Six languages, matching what `clients.reporting_language` actually contains:
English, Traditional Chinese, Simplified Chinese, German, Japanese, Italian.
**71 notes, 26 of them in a second language.** The drawer has an English ⇄
client-language switch, and an edit belongs to a language rather than to a
finding, so typing in one and switching does not lose the other.

Three details that make it read as written rather than translated:

- **Amounts are localised, not just words.** "USD 7.7m" is not how anyone reads a
  number in Chinese or Japanese, where 萬 and 億 are the units. The Chinese note
  says 768萬美元, the Japanese 292万米ドル.
- **Asset-class names are translated.** Leaving "Commodities" in the middle of a
  German sentence is the same mistake as leaving the whole headline there, only
  smaller. Instrument names are proper nouns and stay as they are.
- **The mandate clause is rebuilt per language**, in four shapes — over a band,
  under a band, over a single-position cap, on the exclusion list — rather than
  reusing the English headline.

This is the floor, not the ceiling. `narrate.py` reads the RM's own notes and
writes something specific to this client and this conversation, which is better.
The drawer labels which one is on screen.

## 11. Layer 3: narration

`engine/narrate.py` drafts the client note. Claude explains and drafts; it never
computes. Three mechanisms make that claim mean something.

**No number reaches a client unless the engine produced it.** The payload carries
an `allowed_figures` list — every numeral the engine itself wrote into that
finding — and the system prompt forbids any other. Afterwards `verify()` reads
the drafts back and checks each numeral against the list. A draft that invents a
figure is kept but marked `unverified`, and the composer disables *Accept* and
names the figures it could not trace.

**Direct identifiers never leave the machine.** Name, exact age, nationality,
residence and booking centre are removed. The draft addresses `[[FIRST_NAME]]`
and the workbench substitutes the real name at render time, locally. For a
client reported to in Chinese, Japanese or Korean it substitutes the whole name,
because a bare given name would be wrong.

`--dry-run` audits every payload. The audit found three real problems:

- The engine wrote the exact age into its own prose ("He is 71."), so it was
  reaching the model through the text rather than the profile. Now banded.
- The purpose-fit rule records `age` among its `numbers`, and the allow-list is
  built from those, so the age was reaching the model as a figure it was
  *permitted to write*. Now dropped before the list is built.
- Two remaining hits are coincidences, not disclosures: 66 sits inside an engine
  figure, and 55 is both a client's age and his mandate's upper equity bound.
  The audit reports them as collisions rather than leaks.

Two disclosures are **retained on purpose and stated**:

- *Tax domicile.* It equals nationality for eleven of twenty clients and it
  drives every tax finding. Hong Kong, Singapore and the UAE levy no capital
  gains tax, and a draft that does not know that gives wrong advice. It travels
  only where the rule turns on it.
- *A place the client named in their own objectives*, such as "a property
  purchase in Singapore in 2027", without which the draft cannot discuss the
  thing being funded.

**The demo never depends on a live call.** Every response is cached under a hash
of the exact payload, prompt and model, so a re-run is free and offline. With no
cache and no key, `build.py` attaches nothing and the composer falls back to the
deterministic template *and labels itself as one*.

It drafts in English and the client's reporting language in one call.
`clients.reporting_language` is not English for six of twenty, including both
demo clients. The composer puts the client's language in the textarea, because
that is what gets sent, with the English alongside for the file.

Model is `claude-opus-5`, with structured output against a JSON schema, prompt
caching on the system prompt across all calls, and server-side refusal fallbacks
enabled. `engine/` is Python 3.9 standard library only; this one script needs
3.10+ for the SDK and writes plain JSON, so nothing else gains a dependency.

---

## 12. The interface

**The dossier is four tabs**, because the RM has four different jobs on it:
decide what to raise, look at the money, test a shock, remember who the person
is. They are named **To raise · Portfolio · Scenario analysis · Context**.

**The header carries the standing facts in two labelled rows**, not one that
wrapped wherever the viewport chose:

- *Who*: id, age, nationality, residence, tax domicile, booking centre,
  reporting language.
- *Relationship*: client since, KYC review due (red inside 90 days), PEP status,
  risk profile, liquidity need, horizon.

**The metric strip carries two kinds of number and says so.** On the left, what
the book *is*: clients, assets, findings. On the right, what it *asks of her*:
act, review, watch — each one a filter. A vertical rule divides them.

**Performance.** Three things the dossier could not answer before:

- *Return.* Unrealised return on cost, and separately the change in wealth
  across the five snapshots. Two different numbers, both labelled.
- *Contribution.* Every position's profit and loss expressed in points of that
  same return, so the chart sums exactly to the headline. CL-0012's −12.4% is
  −10.69pp of it in one Treasury.
- *Attribution.* Events from `event_log.csv` matched to the client's own
  holdings and placed on the wealth line at the window they fall in. The match
  requires **every** discriminating word of a phrase. A word the instrument
  universe never uses ("duration", "havens") is dropped as unable to
  discriminate. That rule is what stops "European fixed income" landing on a US
  Treasury through the word "fixed", which the first version did. An event is
  placed beside a move, never asserted as its cause.

**Silence is reported too.** A rule that does not fire leaves nothing on screen,
and nothing on screen looks the same as nobody having looked. The Context tab
states the arithmetic behind every silence:

> "USD 133k falls due inside twelve months against USD 18.3m sellable at daily
> liquidity — 137.4x cover. The funding rule reports below 3x, so it stays
> silent for this client. Silence here means covered, not unexamined."

Every dated obligation carries its own cover figure whether or not it becomes a
finding. Per-row cover is the whole daily-liquid pool against one obligation, so
the rows deliberately do not add up: CL-0006 is comfortable against each of his
two obligations (2.5x, 4.2x) and short against both at once (1.1x). The table
says so.

**The RM can add notes.** A note written in the workbench is stored separately
from `rm_notes.json` and marked as hers, with the limitation stated: the engine
has already run, so a note added now has not changed any finding until it is
written back to source and the engine re-run.

**The calendar.** `upcoming.py` emits every dated obligation with a stable id
and a `spotlight` flag marking the agenda set. `calendar.js` renders them as
agenda, month or week, and lets Priscilla edit: move a date by form or by
dragging a chip, correct a description, add a meeting, hide a row already dealt
with. Her edits are stored as patches keyed by id, so a rebuild never overwrites
them and an edited engine row can always be restored. Month and week open on
today, except when the period is empty, which reads as a broken grid.

The tier tiles scope the calendar as well as the table, and a scoped agenda
**groups by client**. This matters more than it sounds. Pressing "5 Act" used to
open a flat list of eight rows, because three of those five clients owe more
than one thing and the list was also capped at eight. The tile said 5, the
caption said 11 and the list showed 8, so the reader had to reconcile three
numbers before trusting any of them.

Grouped, the number of names on screen is the number on the tile. Each client's
obligations sit under their own name with a count beside it, clients are ordered
by whichever obligation lands first, and nothing is truncated — the panel
scrolls instead, so the caption's count and the reachable rows are the same set.
The caption reads "5 clients in view · 11 dated obligations between them".

Verified for all three tiers and all eight dimension filters: names on screen
always equal rows in the table beside them.

**Interaction.** Everything that navigates is clickable and keyboard-reachable:
table rows, scatter dots, diary entries, calendar cells and chips, tier tiles.
Charts have a staggered entrance armed on scroll-into-view, played on a change of
screen rather than on every render. Renders that do not animate paint everything
visible outright, so an entrance is never the reason something is missing.

**Layout.** The shell is capped at 1290px and body prose at 900px, set in one
CSS variable (`--measure`) in pixels rather than characters, so a 16px
standfirst and a 12px footnote end at the same right edge instead of two ragged
ones. Evidence charts share that edge.

---

## 13. The charts

All inline SVG. No chart library.

The palette is **porcelain** from the `lieflat-charts` skill — a single-hue
ladder where lightness carries the data — re-based onto the values in
`design.md` (canvas `#F3F2E8`, navy `#141B4B`, blue-greys `#969CB2` and
`#CED1DC`). Red is allowed and is a deep brick `#8C2F2A`, never a bright one. It
marks act-tier clients, the LTV trigger and its breaches, and the largest
beyond-horizon maturity.

Chart structures come from the skill's templates rather than being re-skinned
versions of something else. Gallery source is
`~/.claude/skills/lieflat-charts/templates/basics-gallery.html`; find a chart by
its `// ════ name ════` comment.

| Chart | Template | What it shows |
|---|---|---|
| Book: severity against wealth | F8 Plumb Scatter | Wealth across, severity up, tier thresholds drawn in. Hover opens a card with the client's dimensions. The point is that the tall dot is not the rich one. |
| Book: the diary | — | Dated obligations, agenda / month / week |
| Dossier: wealth through the period | B2 Hairline Line | Five dated snapshots on a real time axis, one tick per month. Event markers hang off the floor. The scenario bracket sits to the right of today. |
| Dossier: what moved the return | C5 Rung Waterfall | Contributions that sum exactly to the headline return |
| Dossier: where the money sits | C3 Stacked Rungs | One ladder per snapshot, one rung per two points of wealth |
| Finding: maturity ladder | F12 Dumbbell Queue | Each income position from today to maturity, with the horizon cutting across |
| Finding: LTV path | B2 Hairline Line | Five snapshots against the margin trigger |
| Finding: funding | C1 Tick Rows | Six amounts as countable ticks, LTV strip underneath |

Three notes on why these and not something else:

- **The wealth line uses a monthly floor** because the five snapshots are 31 Dec,
  27 Feb, 31 Mar, 30 Jun and 26 Aug, and the earlier chart spaced them evenly by
  index, which was quietly dishonest.
- **Where the money sits used to be a stacked area.** A continuous ribbon
  between five dated observations implies readings that were never taken. Five
  ladders say five days.
- **The one non-blue in the data palette** is a muted antique gold `#9A7B35`,
  used in exactly one chart. Porcelain's contract is that lightness is the data,
  and that holds wherever a chart encodes an ordered quantity. Asset-class
  sleeves are not ordered, they are categories sorted by size, so the second
  sleeve gets hue as well as lightness. The gold sits at L*≈45, between navy
  (L*17) and blue-grey (L*63), so the ladder still runs dark to pale.

**The funding chart is the clearest single piece of evidence in the product.**
CL-0014's daily-sellable collateral is worth **HKD 88.8m at market and HKD 52.1m
as security**. Raising HKD 60m against it removes more borrowing capacity than
the sale brings in: CF-0002 goes 69.4% → 119.9% against a 70% trigger, and he
must repay HKD 24.1m first. The two rows sit one above the other so the reader
can see why "sell some liquid assets" is what causes the margin call.

The rows and the tick unit come from `liquidity._funding_chart`, not from the
browser. They are figures, and figures come from the engine.

Charts that sit inside a finding render from that finding's own `numbers`. A
chart is evidence, not decoration.

---

## 14. The data traps

Every one of these is real in this dataset. Four were mistakes we made and then
corrected.

| # | Trap |
|---|---|
| 1 | **Cash needs are in local currency.** HKD 60m is USD 7.7m; JPY 18m is USD 113k. Summing the raw `amount` column against USD wealth invents shortfalls. |
| 2 | **Fund from unpledged assets first.** Routing every sale through the pledged portfolio falsely blocks clients holding a large unpledged custody account. `free` decides the routing test only; cover uses total daily liquidity. |
| 3 | **Lending value is not market value.** Advance rates run 0-90%. Illiquid alternatives carry 0%. |
| 4 | **Tax domicile, not residence.** They differ for 7 of 20. Hong Kong, Singapore and the UAE levy no capital gains tax. |
| 5 | **Custody is wealth but not mandate.** Three portfolios are `service_model = Custody`. Include in wealth and concentration; exclude from every band test. |
| 6 | **Structured products hide their exposure.** Nine carry `underlying_reference`. Derived, not hardcoded — see `loader._build_lookthrough`. |
| 7 | **A waiver is not an acknowledgement.** Only CL-0007's note carries waiver language. CL-0002 and CL-0013 acknowledged and proceeded; those breaches stand. |
| 8 | **Objective and cash-needs row disagree.** CL-0012: objectives say USD 1.1m a year, `planned_cash_needs` says 1.28m. Surface both, pick neither. |
| 9 | **One mark is a year stale.** `SYN-AL-0308` is marked 2025-09-30 at all five snapshots and is 68% of CL-0002's wealth. |
| 10 | **Fields are missing.** CL-0017 has no `age` — it is a family office. It crashed the first triage run. |
| 11 | **Six clients do not read English**, including both demo clients. See `clients.reporting_language`. |
| 12 | **`due_from` is a recurring need's first occurrence, not its only one.** CL-0012's living expenses run 2026-01-01 to 2038-01-01: twelve more drawdowns of USD 1.28m. The diary dropped any row whose `due_from` had passed, so his next one vanished from the calendar while the funding rule went on counting it. `upcoming.next_occurrence` now rolls Annual needs forward. |
| 13 | **Two cash-needs rows differ by two characters.** CN-007 is CL-0006's "**US** university fees, two children", USD 5.0m. CN-010 is CL-0008's "University fees, two children", SGD 420k. Different clients, different currencies, dates a year apart. |
| 14 | **A cash-needs row can restate the commitments.** CL-0017's "Outstanding private markets commitments, USD 15.8m" *is* the sum of his two uncalled funds (14.0m + 1.8m). Counting both inflated his 12-month need to 32.5m and invented a funding strain. Guarded in `liquidity._needs` and `upcoming.build`. |

Two conventions worth knowing: bond quantities are in units of 100 nominal, so
`quantity x price_local = market_value_local` holds for every asset class; and
private markets marks lag a quarter by design.

---

## 15. The demo

The brief asks for depth on two or three clients rather than breadth across
twenty.

**CL-0012, Cheung Kwok Wing — opens.** The README's own illustration of a
winning insight is this client, verbatim: 71, retired, drawing USD 1.1m a year,
bond portfolio down USD 5.6m, longest bond maturing 2045. The judges published
their gold standard and left him in the data. 34.9% of his wealth matures after
his 2038 horizon and is USD 4.9m underwater. He told Priscilla he would rather
wait. He is Hong Kong domiciled, so there is no capital gains tax: the loss he
refuses to crystallise buys him nothing.

**CL-0014, Lau Chi Ming — proves the engine.** CF-0002 at 69.4% LTV against a
70% trigger, and a confirmed HKD 60m obligation. PF-0016 holds HKD 88.8m of
daily-sellable assets carrying HKD 52.1m of lending value. Selling HKD 60m
releases about HKD 35.2m of it and takes LTV to roughly 120%. He must repay
about HKD 24.1m first. Then the rate scenario reaches the same trigger by a
different route.

**CL-0005, Aishah binti Rahman — closes on governance.** A *discretionary*
Sustainable Balanced mandate holding two `sustainability_excluded` instruments.
Her note: "She was not aware of the energy fund holding." The bank's error in a
mandate the bank controls, which is why she ranks first at USD 19.4m.

**CL-0007 is the counterpart, a suppression.** He is 8.9 points over his
commodity ceiling and the workbench does *not* raise it: "Suitability waiver on
file." It appears under "Governed, and deliberately not raised" with the quote.

Bench: CL-0004 is CL-0012's mirror, with the same structural problem and a
Thailand domicile, so his losses are genuinely harvestable. CL-0019 asked for a
Strait-reopens scenario his RM could not answer. CL-0011 is 78, in declining
health, with no succession structure and an illiquid estate.

Top of the current ranking: CL-0005, CL-0002, CL-0014, CL-0001, CL-0003,
CL-0012.

---

## 16. Decisions already made

Do not reopen these without a reason.

- **Standard library only, no pandas.** The machine has Python 3.9 with no
  pandas, and the dataset is 1,015 rows. Zero install is worth more at a
  hackathon than convenience.
- **No build step, no framework.** `findings.js` loads as a plain script so the
  workbench opens from `file://`.
- **Severity dominates ranking; count is a tiebreak.** An additive score buried
  CL-0005's compliance breach at rank 10.
- **Severity ceilings do not saturate.** An earlier calibration put nine clients
  in the act tier.
- **Severity is engine-side and rebuilt; weights are RM-side and live.** The
  tempting alternative lets her drag every constant in the browser, which means
  re-deriving severities in JavaScript from raw drivers. That loses the layer
  boundary for a slider. The split holds the line and still answers the
  question, because the whole calibration table is shown in the panel,
  read-only.
- **Look-through is derived, not hardcoded.** Parsing `underlying_reference` and
  the `ref. X` name pattern found exposures a hand-written map missed: Golden
  Harbour across three wrappers at 29.5%, Pacific Orient at 24.3%.
- **One visual theme.** `design.md` commits to warm ivory and deep navy, painted
  explicitly rather than inherited. It was revised mid-project; read it rather
  than assuming the values quoted here are current.
- **Scenario analysis is in scope; price forecasting is not.**

Out of scope: a general chatbot, trade execution, a full optimiser, actual tax
computation, multi-RM views.

---

## 17. How it scores

Four criteria at 25% each.

| Criterion | Where it is earned |
|---|---|
| Client-Centric Innovation | Findings no statement shows: purpose fit against a lifespan, funding joined to collateral, look-through concentration, advice grounded in the RM's own notes |
| User Experience & Design | Three screens; the book sorted by consequence, not AUM; every number opens its rule; each finding ends in a draft |
| Technical & Operational Feasibility | The layer boundary, de-identified payloads, an audit that runs, batch scalability, graceful degradation when the model is down |
| Strategic Impact | The RM stays central: accept / amend / dismiss, dismissal reasons written back, referral to wealth planning where the tool should stop |

The brief also says it assesses four things directly: reasoning you can defend,
judgement about what matters, honesty about uncertainty, and the human in the
loop. Uncertainty is in the schema — `confidence` and `check` fields, certainty
grades carried through, contradictions surfaced unresolved.

---

## 18. How to verify a UI change

`app/app.js` renders three screens from one bundle, and a screenshot of the book
view exercises almost none of it. A missing function in the dossier path stayed
invisible through a whole round of "no errors" checks because the book view
never calls it.

Before claiming a change works, open every client on every tab and catch throws:

```html
<!-- append to a copy of app/index.html, load it headless, grep #RESULT -->
<script>
window.addEventListener("load", () => {
  const bad = [];
  Object.keys(B.clients).forEach(cid =>
    ["raise","money","shock","context"].forEach(t => {
      try { state.view="client"; state.client=cid; state.tab=t; renderClient(); }
      catch (e) { bad.push(cid + "/" + t + ": " + e.message); }
    }));
  const p = document.createElement("p"); p.id = "RESULT";
  p.textContent = bad.join(" | "); document.body.appendChild(p);
});
</script>
```

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
  --disable-gpu --dump-dom --virtual-time-budget=9000 \
  "file://$PWD/app/_test.html" | grep -o 'id="RESULT">[^<]*'
```

Three things learned the hard way:

- Chrome's `--virtual-time-budget` advances timers but **not** the CSS animation
  clock, so an unfinished entrance looks like a missing chart. Force `.shown` on
  `[data-reveal]` before judging one.
- `--screenshot` does not reliably follow a programmatic scroll. Assert on
  rendered text rather than on an image when the target is below the fold.
- When patching with a script, report per-edit success rather than asserting.
  One failed assertion discards every edit in the batch, silently. And
  `node --check app/app.js` catches syntax errors but never a deleted function.

---

## 19. What is left

1. **Run `engine/narrate.py`.** Built and tested; it needs an API key to fill
   the cache. Until then every draft falls back to the template and says so.
2. **Rehearse the four-minute demo.** The spine is CL-0005 (governance, and a
   plan that escalates rather than proposing the sale of a family asset) →
   CL-0014 (the funding chart, then the rate scenario that reaches the same
   trigger a second way) → CL-0012 (purpose fit, and a note he can read).
3. Fold the event timeline into the dossier from `build/dashboard.html`.
4. **Translate an amendment.** Editing a draft does not change the other
   language, and neither the templates nor `narrate.py` can help — both produce
   text before she touches it. Doing it properly needs a call at the keyboard,
   which means a small server holding the key rather than a `file://` page. The
   workbench states the limitation rather than hiding it; closing it is a real
   piece of work, not a tweak.
5. **Let the RM state her own scenario.** Scenarios are a fixed list today. The
   same panel that holds the ranking weights is the obvious place, and the
   module is already shaped for it.

Smaller, if there is time: the calendar's month grid shows dots rather than
titles at 396px, and a wider column would let the chips carry text. Diary edits
are per-browser like every other decision in the workbench, which is worth
saying on stage before someone asks.
