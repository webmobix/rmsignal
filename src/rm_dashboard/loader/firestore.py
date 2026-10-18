"""Writing to Firestore: the source tables (one collection each) and, through ``FirestoreArtifactStore(writable=True)``, artifacts.

Document ids are deterministic and writes go in batches, so a load that fails part-way is completed by running it again with the
same arguments; ``--replace`` deletes what the loader owns first. A marker document is written last, and only a target that holds
the marker counts as already loaded."""

from rm_dashboard.data.dataset import parse_dataset
from rm_dashboard.data.schema import ENTITIES, document_id, to_document
from rm_dashboard.firestore_client import open_client

from .artifacts import LoadError

META = "_meta"
MARKER = "source"
BATCH_OPS = 400


def _delete_all(client, collection: str) -> int:
    refs = [d.reference for d in client.collection(collection).stream()]
    for i in range(0, len(refs), BATCH_OPS):
        batch = client.batch()
        for ref in refs[i:i + BATCH_OPS]:
            batch.delete(ref)
        batch.commit()
    return len(refs)


def load_source_to_firestore(data_dir, location: str, replace: bool = False) -> dict[str, int]:
    """Validate the dataset (raises DatasetError, writing nothing), then write every table. Raises LoadError."""
    parsed = parse_dataset(data_dir)
    client = open_client(location)
    marker = client.collection(META).document(MARKER)
    started = False
    try:
        if marker.get().exists and not replace:
            raise LoadError(f"firestore:{location} already holds source data; use --replace to rebuild it")
        if replace:
            started = True
            marker.delete()
            for e in ENTITIES:
                _delete_all(client, e.table)
        counts: dict[str, int] = {}
        for e in ENTITIES:
            records = parsed[e.table]
            for i in range(0, len(records), BATCH_OPS):
                batch = client.batch()
                for n, rec in enumerate(records[i:i + BATCH_OPS], start=i + 1):
                    batch.set(client.collection(e.table).document(document_id(e, rec, n)), to_document(e, rec, n))
                batch.commit()
                started = True
            counts[e.table] = len(records)
        marker.set({"tables": counts})
        return counts
    except LoadError:
        raise
    except Exception as e:
        hint = "; the target may hold part of the load: run the same command again to complete it" if started else ""
        raise LoadError(f"{type(e).__name__}: {e}{hint}") from e
