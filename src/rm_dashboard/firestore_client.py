"""The one place that imports the Firestore client library, so it stays an optional dependency.

The project and credentials come from the environment (Application Default Credentials); the client library itself honours
``FIRESTORE_EMULATOR_HOST``. Nothing here embeds, prints or logs a credential."""

import importlib
import re

INSTALL_HINT = "Firestore support needs the optional client library: install it with `uv sync --extra firestore` (or `pip install 'rm-dashboard[firestore]'`)"
DEFAULT_DATABASE = "(default)"
_NAME = re.compile(r"^[A-Za-z0-9._\-()]+$")


def parse_location(spec: str) -> tuple[str | None, str]:
    """``<project>[/<database>]`` -> ``(project, database)``; an empty project means the one the environment names."""
    project, _, database = spec.partition("/")
    for part in (project, database):
        if part and not _NAME.match(part):
            raise ValueError(f"invalid Firestore project or database {part!r}: expected firestore:<project>[/<database>]")
    return (project or None), (database or DEFAULT_DATABASE)


def firestore_module():
    """``google.cloud.firestore``. Raises ImportError with the install command when the library is missing."""
    try:
        return importlib.import_module("google.cloud.firestore")
    except ImportError:
        raise ImportError(INSTALL_HINT) from None


def open_client(spec: str):
    """A Firestore client for ``<project>[/<database>]``."""
    project, database = parse_location(spec)
    return firestore_module().Client(project=project, database=database)


def where(query, path: str, op: str, value):
    """``query.where`` with a keyword filter where the library has one (positional arguments are deprecated there)."""
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
    except ImportError:  # the in-memory fake used by the tests has no library behind it
        return query.where(path, op, value)
    return query.where(filter=FieldFilter(path, op, value))


def document_id_field():
    """The path that names a document's id in a query."""
    try:
        from google.cloud.firestore_v1.field_path import FieldPath
    except ImportError:
        return "__name__"
    return FieldPath.document_id()
