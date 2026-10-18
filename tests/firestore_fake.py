"""An in-memory stand-in for the part of the Firestore client the application uses: collections, documents, batches, queries on
a field or on the document id (range, equality), ``order_by``, ``select``, ``get_all`` and ``stream``. It enforces the limits the
real service has and a careless caller would hit: 500 operations and a document size per commit, and no ``/`` in an id."""

import threading

MAX_OPS = 500
MAX_DOC_BYTES = 1_048_576
MAX_COMMIT_BYTES = 10 * 1024 * 1024


def _size(data: dict) -> int:
    return sum(len(str(k)) + (len(v.encode()) if isinstance(v, str) else 8) for k, v in data.items()) + 32


class FakeDoc:
    def __init__(self, ref: "FakeRef", data: dict | None):
        self.reference, self.id, self._data = ref, ref.id, data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict:
        return dict(self._data or {})

    def get(self, field):
        return (self._data or {}).get(field)


class FakeRef:
    def __init__(self, client: "FakeClient", collection: str, id: str):
        if "/" in id or id in (".", "..") or not id:
            raise ValueError(f"invalid document id {id!r}")
        self.client, self.collection, self.id = client, collection, id

    @property
    def path(self) -> str:
        return f"{self.collection}/{self.id}"

    def get(self) -> FakeDoc:
        with self.client.lock:
            data = self.client.data.get(self.collection, {}).get(self.id)
            return FakeDoc(self, None if data is None else dict(data))

    def set(self, data: dict) -> None:
        self.client.apply([("set", self, data)])

    def delete(self) -> None:
        self.client.apply([("delete", self, None)])

    def __eq__(self, other):
        return isinstance(other, FakeRef) and other.path == self.path

    def __hash__(self):
        return hash(self.path)


class FakeQuery:
    def __init__(self, client: "FakeClient", collection: str, filters=(), order=None, fields=None):
        self.client, self.collection, self.filters, self._order, self._fields = client, collection, tuple(filters), order, fields

    def where(self, field_path=None, op_string=None, value=None, *, filter=None):
        if filter is not None:
            field_path, op_string, value = filter.field_path, filter.op_string, filter.value
        return FakeQuery(self.client, self.collection, (*self.filters, (str(field_path), op_string, value)), self._order, self._fields)

    def order_by(self, field):
        return FakeQuery(self.client, self.collection, self.filters, field, self._fields)

    def select(self, fields):
        return FakeQuery(self.client, self.collection, self.filters, self._order, list(fields))

    def stream(self):
        with self.client.lock:
            rows = [(i, dict(d)) for i, d in self.client.data.get(self.collection, {}).items()]
        for field, op, value in self.filters:
            def get(i, d):
                return i if field in ("__name__", "`__name__`") else d.get(field)
            want = value.id if isinstance(value, FakeRef) else value
            test = {">=": lambda a: a >= want, "<": lambda a: a < want, "==": lambda a: a == want, ">": lambda a: a > want, "<=": lambda a: a <= want}[op]
            rows = [(i, d) for i, d in rows if get(i, d) is not None and test(get(i, d))]
        rows.sort(key=lambda r: (r[1].get(self._order) if self._order else r[0], r[0]))
        for i, d in rows:
            if self._fields is not None:
                d = {k: v for k, v in d.items() if k in self._fields}
            yield FakeDoc(FakeRef(self.client, self.collection, i), d)


class FakeCollection(FakeQuery):
    def __init__(self, client: "FakeClient", name: str):
        super().__init__(client, name)
        self.name = name

    def document(self, id: str) -> FakeRef:
        return FakeRef(self.client, self.name, id)


class FakeBatch:
    def __init__(self, client: "FakeClient"):
        self.client, self.ops = client, []

    def set(self, ref, data):
        self.ops.append(("set", ref, dict(data)))

    def delete(self, ref):
        self.ops.append(("delete", ref, None))

    def commit(self):
        self.client.apply(self.ops)
        self.ops = []


class FakeClient:
    def __init__(self, project: str = "demo"):
        self.project = project
        self.data: dict[str, dict[str, dict]] = {}
        self.lock = threading.RLock()
        self.commits = 0
        self.closed = False

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self, name)

    def batch(self) -> FakeBatch:
        return FakeBatch(self)

    def get_all(self, refs):
        for ref in refs:
            yield ref.get()

    def close(self):
        self.closed = True

    def apply(self, ops) -> None:
        if len(ops) > MAX_OPS:
            raise ValueError(f"too many operations in one commit: {len(ops)} (limit {MAX_OPS})")
        total = 0
        for kind, ref, data in ops:
            if kind == "set":
                if _size(data) > MAX_DOC_BYTES:
                    raise ValueError(f"document {ref.path} is over the size limit")
                total += _size(data)
        if total > MAX_COMMIT_BYTES:
            raise ValueError("commit is over the size limit")
        with self.lock:
            self.commits += 1
            for kind, ref, data in ops:
                coll = self.data.setdefault(ref.collection, {})
                if kind == "set":
                    coll[ref.id] = dict(data)
                else:
                    coll.pop(ref.id, None)
