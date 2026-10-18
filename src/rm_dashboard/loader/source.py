"""Loading the dataset files into a source-data backend."""

from pathlib import Path

from rm_dashboard.data import seed
from rm_dashboard.data.dataset import DEFAULT_DATA_DIR, DatasetError
from rm_dashboard.data.factory import parse_spec

from .artifacts import LoadError


def load_source(data_dir: str | Path = DEFAULT_DATA_DIR, target: str | Path = "rm.db", replace: bool = False) -> dict[str, int]:
    """Validate the dataset files and write them to ``target`` (``sqlite:<file>`` or ``firestore:<project>``); rows loaded per table.

    Raises LoadError. Nothing is written when any file is invalid; a SQLite target is all or nothing."""
    try:
        backend, rest = parse_spec(target)
    except ValueError as e:
        raise LoadError(str(e)) from None
    try:
        if backend == "sqlite":
            return seed.seed(rest, data_dir, replace)
        from .firestore import load_source_to_firestore  # lazy: the Firestore client library is optional

        return load_source_to_firestore(data_dir, rest, replace)
    except DatasetError as e:
        raise LoadError(str(e)) from None
