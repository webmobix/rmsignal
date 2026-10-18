# Design

## Context

`FirestoreArtifactStore` already implements batched, deterministic-id writes for the loader, behind a `writable` flag; runners were refused through `check_writable`. Audit and evidence are already one document per entry, under Firestore's 1 MiB limit. See proposal.md.

## Decisions

- **Same class, flag per caller.** `open_store(spec, writable=False)` stays read-only by default so the API cannot write; `store_from_args` (all runner CLIs) passes `writable=True`. Runner functions that receive a read-only store still fail at `check_writable` before any model call.
- **The store marks dates.** `put_many` sets the `runs/<date>` marker after the commit, once per date per store object (cached). Alternative: a runner end-of-stage call; rejected, a crashed stage would leave written artifacts invisible, and the API reads whatever exists.
- **No new atomicity.** Writes are batched commits, not one transaction (unchanged). Runners write evidence before what cites it, as before; a failed run leaves partial artifacts that a re-run replaces.
- **Alternative rejected:** staging in `/tmp` SQLite and loading at the end. It forces all stages into one container and loses everything on failure.

## Risks / Trade-offs

- [Many small writes: one audit entry per document] → acceptable at this scale; `put_many` batching used for evidence. Revisit if runs get slow.
- [Concurrent runners on the same date] → each stage writes its own kinds and audit prefix, so they do not collide; `reconcile`/`actions` still must run after `analyse`.
- [A stage that replaces its results deletes then rewrites] → readers may briefly see a gap; same as the loader's `--replace`.
