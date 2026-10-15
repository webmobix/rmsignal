# BaerSignal — 3-minute pitch, content draft

Content only. Formatting and visual design come later.

## The title

> ## "Sell some liquid assets."
> **The most sensible thing you could tell Lau Chi Ming. It triggers his margin
> call.**

It is a real instruction, not a slogan. The audience reads it, agrees with it,
and then watches it be wrong — which makes the demo the payoff rather than the
illustration of a claim already made. It also survives being said aloud, which a
headline-shaped title does not.

The deck cover currently reads "What breaks next?". Change it, and change the
`<title>` in `Deck/wealth-intelligence-pitch.html` with it.

Two alternatives, if this one feels too narrow:

- **"The statement doesn't show this."** Broader — it covers purpose fit,
  look-through concentration and funding joined to collateral, not just the one
  client. Safer, and weaker as an opening beat, because it is a claim rather
  than a trap.
- **"Twenty clients. One question."** Sets the Monday scene and hands the
  question over. Cleanest, least specific, most forgettable.

**Budget:** 3:00 ≈ 450 spoken words at demo pace. This script is 493 — about 3:17 spoken,
before clicking. Take cuts 1 and 2 and you land near 2:45.

## The flow rule

**The screen only ever moves forward.** Four positions. Everything that has to be
said on a screen is said while you are on it, and you never go back to one.

| | Position | How you get there | Return to it? |
|---|---|---|---|
| 1 | The book | opening screen | never |
| 2 | Lau Chi Ming → **To raise** | click his row | never |
| 3 | The composer drawer | *Draft the client note*, on the finding you are already reading | closes back to 2, then straight on |
| 4 | Lau Chi Ming → **Scenario analysis** | one tab across | end |

Three moves total, all forward. Two earlier drafts of this pitch failed here in
different ways: the first visited three clients, and the second went to the
scenario tab and then had to come *back* to the To raise tab to open the
composer, because the *Draft the client note* button only exists on a finding.
Opening the composer before moving to the scenario tab is what removes that.

**The one deliberate trade:** the pitch now ends on the scenario rather than on
the client note. If you would rather close on the note, swap scripts F and G —
but that is the backtrack, so only do it knowingly.

**Shape:** one client, all the way down. Three minutes buys one deep client, not
five shallow ones, and the brief asks for depth explicitly.

---

## ⚠️ Read before you present

**1. Two currencies are on that screen, and the script now follows your finger.**
CL-0014's stat strip reads **11.38m — sellable at daily liquidity, USD**. The
funding chart below it reads **HKD 88.8m**. Same number: USD 11.38m × 7.81 = HKD
88.8m. The strip is USD because the whole book is; the chart is HKD because that
is what he owes in.

An earlier draft said "eighty-eight point eight" while 11.38m was the number on
screen. Script C now speaks USD while you are pointing at the strip, and switches
to HKD at the moment you point at the chart — the change of currency happens when
the reader's eye moves, which is the only way it is not jarring. **Say the
numbers in the order the script has them, and point at what you are saying.**

**2. Do not claim the scenario is rule-computed.** An earlier draft said
"everything I just showed you was computed by a rule" *after* showing the
scenario tab. The scenario's arithmetic is deterministic Python, but the shock
itself is a hand-written assumption. The trust claim now sits in script D, on the
To raise tab, where it is exactly true, and the scenario states its own different
status in script G. That ordering is a stronger pitch, not a weaker one: it shows
the product distinguishes a computed fact from a stated assumption.

**3. The close works with or without an API key.** The drawer opens on the
Traditional Chinese note either way — the deterministic notes are written
engine-side in six languages, with an English ⇄ Traditional Chinese switch on the
panel. With `narrate.py` run it *also* shows "Drafted by Claude" and the green
figure-verification block; use script F1 then. Without it the tag reads
"Template" and there is no verification block; use F2. Both are true sentences
about what is on screen. Just do not read F1 over a screen showing F2.

---

## Position 1 — The book

**On screen:** the book view. Do not click into anything. Everything about the
whole book is said here, now, and you never come back.

### Script A — the problem (0:00–0:20)

> Priscilla Ong covers twenty clients and five hundred and ninety-six million
> dollars at Julius Baer's Asia desk. It is Monday.
>
> Her systems sort this book by assets, by performance, by last contact — none of
> which answer the only question she has. Who breaks first?

### Script B — the answer, the diary, the control (0:20–0:55)

**Action:** gesture at the scatter, then at the calendar beside it, then at the
*How this is ranked* button. Say the retune rather than opening the panel —
opening it is a modal you would have to close, and the sentence lands without it.

> This is that answer. Twenty clients in order of their most serious open issue —
> and the tall dot is not the rich one. Attention does not follow assets.
>
> Beside it, everything that is actually dated: promises, capital calls, KYC
> reviews. It follows whatever the book is asking, so pressing *Act* gives you
> those five clients' obligations and nobody else's.
>
> And the ranking is hers. She sets how much each kind of problem counts, and the
> book reorders. Seventy-one findings underneath it.

**Criteria hit:** Client-Centric Innovation; Strategic Impact — the RM's
judgement, not the vendor's.

---

## Position 2 — Lau Chi Ming, To raise

**On screen:** click his row. You land on the funding finding and its chart.
**Stay here for three scripts**, then open the composer without leaving.

### Script C — the trap (0:55–1:45)

**Action, in this order.** Point at the **stat strip** for the first two
sentences — 26.49m and 11.38m are both there, in USD. Then **scroll to the
funding finding and its chart** and stay on it. The currency changes when your
finger moves, and not before.

> Lau Chi Ming. Twenty-six and a half million dollars, eleven point four of it
> sellable within a day.
>
> He has committed seven point seven million — sixty million Hong Kong dollars —
> to a property deal, due November. Eleven against seven. Every tool would tell
> him he is covered: sell some liquid assets.
>
> That advice is what causes the margin call. This chart is in Hong Kong dollars
> now, because that is what he owes in. The assets he would sell are the
> collateral for his credit facility, and as security they are worth fifty-two
> million, not the eighty-eight they fetch at market. Selling sixty destroys more
> borrowing capacity than the sale raises: sixty-nine per cent loan-to-value goes
> to a hundred and twenty, against a seventy per cent trigger.

**The line to land:** *the obvious advice is the thing that breaks him.*

**Why no statement shows this:** it needs three files joined — holdings, credit
facilities, planned cash needs — and the knowledge that lending value is not
market value.

### Script D — why you can trust it (1:40–2:00)

**Action:** open *Why this fired, and where the numbers came from*. It expands
inline; nothing to close.

> Every number on this screen was computed by a rule, in Python. Not one of them
> came from a language model. That is the one architectural line in this product,
> and this is what it buys: open any figure and you get the rule, the rows it
> read, and the arithmetic that produced it.

**If a judge notices two cards about the same sixty million:** they are meant
to. A dated promise being large and that promise being unpayable are different
questions with different answers, so both keep a card — and each says on its face
that it is the same obligation as the other, and that it counts once toward his
rank. That is not a duplicate; a duplicate would be one that did not say so.

### Script E — judgement (2:00–2:18)

**Action:** scroll down to a position-limit finding and its plan table — the
*Not sold* rows.

> It also tells her what it will *not* do. Three trades here would fix his
> position limits, and all three are blocked: weekly dealing, not daily. Not a
> Monday trade.
>
> A tool that proposes trades she cannot place is one she stops trusting by
> Wednesday.

**Criteria hit:** Technical & Operational Feasibility, and "reasoning you can
defend". Script D is the slide that wins the governance mark.

---

## Position 3 — The composer drawer

**On screen:** click *Draft the client note* on the finding you are already
reading. It opens over the same page. Click **English** on the language switch,
then click back to Traditional Chinese. Do not narrate the click — let it land.
Close the drawer at the end of the script.

### Script F1 — use if `narrate.py` has been run (2:18–2:38)

> Every finding ends here. A note written from the finding and never from the
> portfolio, in Traditional Chinese because that is what he reads, with the
> English beside it so Priscilla can read what she is signing — and every numeral
> checked against the figures the engine published. A draft that invents a number
> cannot be sent.

### Script F2 — use if it has not (2:18–2:38)

> Every finding ends here, in the language the client actually reads, with the
> English beside it so Priscilla can read what she is signing. No model was
> needed for this one — the wording is written into the engine in six languages,
> and every figure in it came from the rule.

---

## Position 4 — Scenario analysis

**On screen:** one tab across from where the drawer closed. Select "Long rates
rise another 100bp".

### Script G — the second route, the caveat, the close (2:38–3:00)

> One last thing, one tab across. If long rates add another hundred basis points,
> the same facility crosses the same trigger by a different route. Same margin
> call, nothing to do with the property deal.
>
> And this one is not a rule. The arithmetic is — but the shock is an assumption
> a person wrote down, so we print where it came from and what it gets wrong. We
> never call it a forecast.
>
> Monitoring tells her what happened. This tells her what to do on Monday.

**Criteria hit:** honesty about uncertainty. Say "assumption" out loud; it is
worth more than pretending to predict.

---

## 8. Timing

| Position | Script | Ends | Words |
|---|---|---|---|
| 1 The book | A the problem | 0:20 | 45 |
| 1 The book | B answer + diary | 0:55 | 82 |
| 2 To raise | C the trap | 1:45 | 129 |
| 2 To raise | D trust | 2:02 | 54 |
| 2 To raise | E judgement | 2:20 | 45 |
| 3 Composer | F2 the note | 2:40 | 51 |
| 4 Scenario | G close | 3:00 | 87 |
| | | | **493** |

---

## 9. Cut list, in order

Cut in this order. Every cut leaves the argument standing.

The script is 493 words, which is over. **Cuts 1 and 2 are not optional** —
take both and you are at 418, about 2:47, which is where you want to be.

1. Script B's last sentence — the retune and the totals. Keep the diary; it is
   newer and it does more work. (−30 words, ~12s)
2. Script E entirely. The judgement point survives as the first Q&A answer.
   (−45 words, ~18s)
3. Script C's last clause — the loan-to-value numbers. The trap already landed on
   "destroys more borrowing capacity than the sale raises". (−24 words, ~10s)
4. Script A's list of what her systems *can* sort by. Go straight to "who breaks
   first". (−17 words, ~7s)

Do **not** cut script D. Without it every number in the pitch is an assertion,
and that is the mark this competition is actually scored on.

---

## 10. Q&A backup

**"Have you got another example?"**
Two, and they are why the tool is usable rather than merely correct. One client
is nearly nine points over his commodity limit and we deliberately do **not**
raise it — he instructed the purchase after being warned, and the waiver is on
file. Another holds a palm-oil position that breaches her sustainability mandate,
but her notes record it as a family asset from before the policy, so the tool
refuses to propose selling it and escalates instead. It never quietly drops a
binding breach either.

**"What about the client the brief itself describes?"**
That is CL-0012, and he is in there: seventy-one, retired, drawing 1.1m a year,
holding bonds that mature seven years after his horizon and 4.9m underwater. He
will not sell at a loss — and because Hong Kong levies no capital gains tax, that
loss buys him nothing. He is the better story and the slower explanation, which
is why he is here and not in the three minutes.

**"Are the scenarios forecasts?"**
No, and the interface never says "will". Each is a stated shock repriced. The
event log gives the *size* of a move of that kind when one really happened, so
the numbers are argued from evidence rather than invented — but none of the four
has happened to these holdings, and three are not replays at all. The Hormuz
scenario is the recorded closure run backwards.

**"So what does the model actually do?"**
Prose, and only when it has been run. It reads the RM's notes and explains the
finding in language specific to that client. It never computes. Note that the
client-facing notes exist without it, in six languages, written into the engine —
so the product degrades to a worse note, not to no note.

**"Can she edit the note and have it translated?"**
No, and we say so on the screen. Editing one language does not change the other,
because both are produced before she types: the engine's frames are fixed
sentences, and the model layer drafts when the engine is built, not at the
keyboard. When one version has been edited and the other has not, the composer
says the two no longer agree. Translating an amendment needs a call at the
keyboard, which means a server holding a key — we chose to state the limit rather
than add that dependency.

**"What is it wrong about?"**
Three things we print on screen. The scenario module carries no duration, so
every bond takes the same move — for a 2045 Treasury against a 2028 that is
wrong. It nets nothing against a hedge, because the dataset records none. And a
note typed into the browser has not changed any finding until it is written back
to source and the engine re-run.

**"How much of this is real?"**
All of it runs. `python3 engine/build.py`, then open a file — no server, no
install, Python standard library only.

---

## 11. Every figure used, and where it comes from

Check these before presenting. All are engine output.

| Figure | Source |
|---|---|
| 20 clients, USD 596.2m | `clients.csv` + `holdings.csv` via `loader.wealth` |
| 71 findings, 28 plans, 4 scenarios | `build.py` terminal output |
| HKD 60m, due 2026-11-01 | `planned_cash_needs.csv`, CN-013 |
| HKD 88.8m market / 52.1m lending value | `liquidity._funding_chart`, CL-0014 |
| USD 11.38m on the stat strip | the same 88.8m, ÷ 7.81 |
| USD 26.49m total wealth | stat strip |
| USD 7.7m = the HKD 60m obligation | `LIF-CN-013`, `numbers.usd` |
| 69.4% → 119.9%, 70% trigger | `FUN-CL-0014` |
| Three trades blocked, weekly not daily | `rebalance.plan_for_limit`, PF-0016 |
| Rates +100bp → 70.2% | `scenario.py`, `rates_up_100`, CF-0002 |
| Six languages, 26 notes in a second one | `clientnote.build` |
| Nearly nine points over the limit (Q&A) | `MAN-PF-0009-COMM`, waived, note N-010 |
| Palm holding protected and escalated (Q&A) | `rebalance.plan_for_exclusion`, CL-0005 |

The commodity breach is 8.9 points. Say "nearly nine" — the screen is visible in
Q&A.

---

## 12. What this pitch deliberately leaves out

Named here so nobody adds them back under time pressure.

- **The two other demo clients** (the waiver, the escalation). Both strong, both
  cost a screen switch. They are the first Q&A answer instead.
- The charts, the calendar, the severity tuner, the look-through concentration
  engine. Good work; none survives a three-minute cut.
- The fourteen data traps — the most technically impressive thing in the
  repository, but a pitch is not a code review. If a judge asks "what was hard?":
  trap 2 (fund from unpledged assets first) and trap 12 (`due_from` is a
  recurring need's *first* occurrence, not its only one).
