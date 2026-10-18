"""Backend-agnostic persistence for generated artifacts."""

from .base import GLOBAL, Artifact, ArtifactStore, Kind, ReadOnlyStore, check_writable, log_dir, read_json, read_model
from .factory import BACKENDS, DEFAULT_SPEC, as_store, open_store, sqlite_path
from .sqlite import FILE_NAME, SqliteArtifactStore

__all__ = ["Artifact", "ArtifactStore", "BACKENDS", "DEFAULT_SPEC", "FILE_NAME", "GLOBAL", "Kind", "ReadOnlyStore",
           "SqliteArtifactStore", "as_store", "check_writable", "log_dir", "open_store", "read_json", "read_model", "sqlite_path"]
