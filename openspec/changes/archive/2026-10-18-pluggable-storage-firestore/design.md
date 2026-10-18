# Design

## Context

Source data is read through `SqliteDataSource`; `PolarsPitRepository` only calls its 12 `list_*()` methods and loads everything into memory at startup. `api/sources.py` additionally uses `select`, `count` and `get_by_key`. Artifacts are JSON files under `reports/<as_of>/`, reached through `OutlookStore`, `ScenarioStore`, `CatalogueStore`, `FolderReportSource` and `FolderOverviewSource`, but also through direct `write_text`/glob/`iterdir` in six runners, `api/evidence.py`, `api/overview.py`, `actions/agent.py` and `AsOfIndex`; the tool context carries `reports_dir: Path`. Sizes today: 526 files, ~20 MB; largest evidence file ~960 KB, `audit.jsonl` 1.3 MB; evidence ids are content hashes (1,334 entries, 802 distinct across clients). See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- One seam for artifacts and one for source data, used by every reader and writer.
- Firestore read support good enough for the demo server; a one-way loader to publish local artifacts and source data.
- No behaviour change for local SQLite use, beyond artifacts moving from folders into `artifacts.db`.

**Non-Goals:**
- Runners writing to Firestore (deferred; the Firestore store refuses writes).
- Cross-document atomicity in Firestore, concurrency control, or the Firestore emulator as mandatory CI infrastructure.
- A query language over artifacts; only get, list-by-prefix and dates.
- Changing the content or schemas of any artifact.

## Decisions

**1. Artifacts are `(as_of, kind, key)` + JSON text, not a path tree.**
`ArtifactStore` is a small Protocol: `put`, `put_many`, `get`, `get_many`, `keys(as_of, kind, prefix="")`, `dates()`, `delete_prefix` (used by replace/force runs). Kinds are an enum of today's folder names (`report`, `reconciliation`, `mandate-reconciliation`, `actions`, `overview`, `outlook-market`, `outlook-instrument`, `scenario-vector`, `scenario-impact`, `scenario-client`, `scenario-rollup`, `scenario-catalogue`, `run-summary`, `audit`, `evidence`, `evidence-index`). Keys are the existing ids joined with `/` (for example `rates-higher-for-longer/PF-0001`). Alternative: keep mirroring paths with a virtual filesystem; rejected because it carries filesystem semantics (mkdir, glob) that neither backend needs.

**2. Typed facades stay; they delegate.** `OutlookStore`, `ScenarioStore`, `CatalogueStore`, report and overview sources keep their method names and return the same pydantic models, built over an `ArtifactStore`. This confines the change to constructors, the runners' write calls and a handful of direct file accesses, and keeps agent and tool code intact. The "unparseable = absent" rule from `ScenarioStore._load` moves into a shared helper.

**3. Evidence is split: one record per result plus an index per subject.**
`evidence/<evidence_id>` holds a `ToolResult` once per date (ids are content hashes, so identical results dedupe); `evidence-index/<subject>` holds the ordered id list. Reading a subject = read index, then `get_many`. This keeps every record far below Firestore's 1 MiB limit, preserves per-subject order, and replaces `find_result`'s scan of all files with a single `get`. Alternative: one record per subject (kept as is) fails at 960 KB; chunking it would still need an index and make lookup by id a scan.

**4. Audit is one record per entry.** `AuditLog` takes a sink; the file sink is replaced by an artifact sink writing kind `audit`, key `<stage>/<seq:08d>`. `run.log` is diagnostic output, not an artifact, and stays a local file.

**5. Atomicity by write order, not transactions.** SQLite `put`/`put_many` run in one transaction. For multi-part results (vector + evidence, impact + evidence) the writer saves evidence first and the main record last, as `ScenarioStore.save_vector` does today, so a reader never sees a main record whose evidence is missing. This also matches how the loader will have to publish to Firestore (batches of up to 500 operations, main records after evidence).

**6. Separate `artifacts.db`.** The source database is opened `mode=ro` by spec and is wiped by `seed --replace`. Artifacts need writes and must survive re-seeding. Default location `reports/artifacts.db`; `--reports-dir` keeps working as "directory containing `artifacts.db`" so existing command lines remain valid.

**7. Firestore layout.**
- Artifacts: one flat collection, doc id `"{as_of}|{kind}|{key}"` with `/` and `%` percent-encoded (Firestore ids cannot contain `/`); fields `as_of`, `kind`, `key`, `body` (JSON text, which avoids Firestore's map/NaN/field-name restrictions), `seq` where order matters. `keys()` is a range query on the doc id prefix, so no composite index is needed. Firestore has no distinct, so a marker doc per date in a `runs` collection is written by the loader and read by `dates()`.
- Source data: one collection per table, doc id = primary key joined with `|` (or `row-{seq:06d}` for holdings, which has none), fields as typed values (date as ISO string, bool native) plus `_seq` for file order, read with `order_by("_seq")`. A small Firestore codec sits beside the existing SQLite one in `data/schema.py` so both derive from the dataclasses.
Alternatives: nested subcollections per date and kind (more reads for `dates()`/`keys()`, no benefit); native maps for bodies (Firestore rejects some float and key shapes, and body reuse of `model_validate_json` is simpler).

**8. Contract tests over both backends.** One parametrised suite for `ArtifactStore` and `DataSource` runs against SQLite and an in-memory fake that mimics the Firestore client surface used (get, set, batch, range queries on id, streaming). Optionally against the emulator when `FIRESTORE_EMULATOR_HOST` is set. This gives parity coverage without GCP.

**9. Loader.** `rm-dashboard-load` with two subcommands: `source` (data dir to SQLite or Firestore) and `artifacts` (SQLite file or `reports/` folder to SQLite or Firestore). Parsing and validation move out of `seed.py` into a backend-neutral function returning typed records per table; seed and loader both call it, then write via a sink. All validation completes before the first write. Firestore writes use deterministic ids and batches, so a failed run is completed by re-running; `--replace` deletes the loader-owned documents first. Importing a `reports/` folder re-chunks evidence and audit into the split form from decision 3/4.

**10. Configuration.** `Settings` gains `artifact_store` (`sqlite:<path>` default, `firestore:<project>[/<database>]`) and `data_source` (`sqlite:<path>` default from `RM_DASHBOARD_DB`, `firestore:<project>`), env `RM_ARTIFACT_STORE` and `RM_DATA_SOURCE`, plus CLI flags on runners and `serve`. Credentials come from Application Default Credentials; the Firestore client honours the emulator host variable itself. Imports of `google.cloud.firestore` are lazy and the extra is `rm-dashboard[firestore]`.

**11. Tool context.** `ToolContext.reports_dir` becomes `artifacts: ArtifactStore | None`. The code that does `dataclasses.replace(ctx, reports_dir=store.base_dir)` in the outlook and scenario agents becomes passing the store through.

## Risks / Trade-offs

- [Wide mechanical refactor across runners, API and tools] → Land the SQLite seam first behind the existing tests, convert one stage at a time, and keep facades' signatures; grep for `write_text`, `read_text`, `iterdir`, `glob` in `src/` as the done check.
- [Firestore read cost and latency on each request] → The API already loads source data once at startup; artifact reads are per-request `get`/`get_many` on a small dataset (~20 MB). Acceptable for a demo; add a per-process read cache only if measured slow.
- [Eager source load from Firestore at startup (~1.7k documents)] → One streamed read per table; accepted.
- [Loader to Firestore is not transactional] → Deterministic ids plus idempotent re-run; validation runs fully before writing; main records written after their evidence.
- [Firestore fake diverges from the real service] → Keep the fake to the few operations used, and run the contract suite against the emulator in one manual pre-demo check.
- [Existing `reports/` folders stop being read] → The loader imports them; document the one-time step in the README.
- [Overlap with `clarify-overview-summary` and `add-market-breadth`] → Rebase after either lands, or land them first; both only touch overview and outlook code that this change re-points.
