# Tasks

## 1. Writable Firestore store for runners

- [x] 1.1 `open_store(spec, writable=)` and `store_from_args` open Firestore writable for runners; the API's store stays read-only. Verify: `tests/test_firestore.py` read-only store refuses writes and a read-only store handed to a runner function fails before any model call.
- [x] 1.2 `put_many` marks each written date in `runs` once; the dateless catalogue is never marked. Verify: `test_a_runner_writes_its_artifacts_to_firestore_and_marks_the_date` passes on the Firestore fake (and the emulator when configured).
- [x] 1.3 Update the READ_ONLY message and module docs. Verify: tests match the new message.

## 2. Docs

- [x] 2.1 Rewrite `docs/deploy-cloud-run.md` for one job per runner on Firestore, README "Demo on Firestore" and `docs/architecture.md`. Verify: no remaining statement that runners cannot write to Firestore.
