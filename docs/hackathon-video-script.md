# RMSignal: demo video script (3:30 to 3:45, hard limit 4:00)

Record the screen at `http://localhost:3000` (as-of 26 Aug 2026) with a voice-over. Read the voice-over at a calm pace: about 130 words a minute. The voice-over is about 445 words (about 3:25 of speech at 130 words a minute). Do a timed dry run. If you are over 3:45, cut the Mandate breach part. Never go over 4:00.

**Before you record**
- API on port 8765, UI on port 3000. Open the Overview page first.
- Close other tabs. Browser zoom 110%. Hide bookmarks.
- Do one dry run. Know the click path below so the video has no dead air.
- Say "the bank's view" and "the RM decides" out loud. Judges listen for the human in the loop.

---

## 0:00 – 0:25 | The problem (Overview page on screen)

**Screen:** Overview page, top of the page.

**Say:**
"Priscilla is a Relationship Manager in Singapore. She has twenty clients and about six hundred million dollars to look after. Her tools show her numbers. They don't tell her who to call first, or why. RMSignal does. It reads every portfolio, market event and note, and gives her a short list: who to call, what to say, and the proof."

## 0:25 – 1:05 | Who to call first (Overview)

**Screen:** Point at the summary sentence, then scroll to the "Needs action now" table.

**Say:**
"This is the Overview. The summary at the top says who needs the first call. Cheung Kwok Wing is holding bonds at a loss, and the bank's view on rates is negative. Below, every action across all twenty clients is ranked by importance and by how soon it matters.
Each action says what to do and why. Let me open one."

**Click:** the first action ("Discuss holding at a loss against the negative rates view"). The evidence drawer opens.

**Say:**
"Every claim links to its source. The data, the calculation, the note. Priscilla can check it in seconds, and she can explain it to the client."

## 1:05 – 1:50 | One client in depth (Client page, CL-0012)

**Screen:** Click the client name. Show **Summary and portfolios**, scroll slowly through portfolio health, combined allocation, look-through table, liquidity against planned needs.

**Say:**
"Here is the client. All his portfolios in one view, because risk hides between portfolios. The look-through table shows what structured products really hold. Liquidity is checked against the money he plans to spend."

**Click:** the **Compare snapshots** tab.

**Say:**
"We have five dated snapshots. Comparing two of them shows what changed, next to the events that happened in between."

**Click:** the **Actions and notes** tab.

**Say:**
"Here the system checks Priscilla's own notes against the numbers. If a note says 'portfolio is fine' and the data says it is not, it flags the difference. It never changes her note. It shows both."

## 1:50 – 2:25 | Mandate breaches (Client CL-0007, then back)

**Screen:** Go to Alistair Pemberton-Hale (CL-0007). Open a portfolio, show the breach section.

**Say:**
"Alistair's commodities are above his mandate ceiling. The system finds the breach with code, then reads the notes. A waiver is on file. The system shows the waiver as the RM's claim. It does not remove the breach. The status says: client-directed. Priscilla decides what to do."

## 2:25 – 3:00 | What could happen next (Scenarios tab)

**Screen:** On a client, open the **Scenarios** tab. Show the three scenarios and the best / likely / worst range.

**Say:**
"The Middle East situation is still open. What if it calms down? What if it gets worse? What if rates stay high? For each scenario we show the change in this client's portfolio in three cases: best, likely and worst. Code does the maths. The AI only writes the explanation. We say clearly on screen: these are not probabilities."

## 3:00 – 3:35 | How it works and why you can trust it (Slide or architecture picture)

**Screen:** Show the pipeline diagram from the pitch deck (or `docs/architecture.md`).

**Say:**
"Behind the screen, a chain of small AI agents. One writes the market view. Analysts study each client. Others check the notes and mandates, and write the actions. Three rules hold everything together. One: agents never do the maths. Code does. Two: every claim must cite evidence, and a check in code deletes any claim with a number that isn't in the evidence. Three: client names are replaced before anything reaches the model. Everything is logged."

## 3:35 – 3:50 | Close

**Screen:** Back to the Overview page.

**Say:**
"RMSignal turns portfolio data into a short, ranked, explained to-do list. Priscilla stays in charge. She decides what to do. We just make sure she never misses what matters. Thank you."

---

## Things to be honest about (say one line if time allows, it scores well)

- The data has gaps. The reports say "partial" and list what is missing, such as related persons and beneficial owners. The system tells you what it could not see.
- Policy checks and the KYC peer are mocks in this MVP.
- Scenario ranges are conditional, not forecasts.

## Time check

| Part | Start | Length |
|---|---|---|
| Problem | 0:00 | 25s |
| Who to call first | 0:25 | 40s |
| One client | 1:05 | 45s |
| Mandate breach | 1:50 | 35s |
| Scenarios | 2:25 | 35s |
| How it works | 3:00 | 35s |
| Close | 3:35 | 15s |

Total: about 3:50 if every slot is used in full. The spoken words are shorter than the slots, so a calm read lands near 3:30. Cutting the Mandate breach part saves about 35 seconds.
