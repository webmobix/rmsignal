# BaerSignal

Deterministic finding engine plus an RM workbench over the SingHacks 2026
Julius Baer dataset. Standard library only — nothing to install.

## Run it

```bash
python3 engine/build.py     # reads data/, writes app/findings.json and app/findings.js
open app/index.html         # no server needed; the bundle is loaded as a script
```

`engine/build.py` prints the ranked book to the terminal as it goes, so the
engine is verifiable without opening the UI.

## The narration layer (optional)

The workbench runs without it: with no drafts on disk the composer falls back to
a deterministic template and labels itself as one. To draft in the client's own
language:

```bash
python3.13 -m pip install anthropic            # needs Python 3.10+; the rest of
                                               # engine/ stays stdlib-only on 3.9
printf '%s' 'sk-ant-...' > ~/.anthropic_key    # or export ANTHROPIC_API_KEY
chmod 600 ~/.anthropic_key

python3.13 engine/narrate.py --dry-run         # show a payload, audit it, call nothing
python3.13 engine/narrate.py                   # fill the cache
python3 engine/build.py                        # fold the drafts into the bundle
```

Responses are cached to `engine/cache/`, keyed by a hash of the exact payload,
prompt and model, so a re-run is free and offline. Nothing about the demo depends
on a live call.

## Layout

```
engine/
  loader.py          canonical data access — FX, custody, look-through, stale marks
  notes.py           structured claims from the RM's free text, with quotes
  narrate.py         Layer 3 — de-identified payloads, cached drafts, numeric check
  performance.py     return on cost, contribution, event attribution
  scenario.py        module F — stated shocks, repriced; never a forecast
  schema.py          the Finding shape every layer agrees on
  severity.py        the 0-100 scale: every calibration constant, and `Sev`
  triage.py          book-level ranking; the weights live here and nowhere else
  build.py           runs the modules and writes the bundle
  modules/
    governance.py    mandate bands, single-position limits, binding exclusions
    liquidity.py     collateral headroom and funding feasibility
    client_fit.py    purpose fit, look-through concentration, life events, stale marks
    tax.py           loss harvesting, gated on tax domicile
    rebalance.py     module E — constrained trades, and the rule that stopped each
app/
  index.html         the workbench
  app.js             renders; the ranking panel is the only arithmetic
  triage.js          a direct port of triage.rank, for the live retune
  calendar.js        the diary as agenda / month / week, editable
  styles.css         the visual system from design.md
  findings.js        generated — the only thing the UI reads
```

## The one rule

A number that appears in the workbench is produced by `engine/`, or it does not
appear. `app/app.js` formats and lays out; it contains no arithmetic over the
dataset. That is what makes every figure clickable back to the rule that made it.
