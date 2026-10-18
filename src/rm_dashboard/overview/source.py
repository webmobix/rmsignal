"""Where the overview reads from: the stored per-client outputs of a date, and the RM's clients."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from rm_dashboard.actions.contracts import ClientActions
from rm_dashboard.mandate_reconciliation import MandateReconciliation
from rm_dashboard.reconciliation import Reconciliation
from rm_dashboard.reportsource import FlatFinding, StoreReportSource, flatten
from rm_dashboard.store import ArtifactStore, Kind, read_model


@dataclass(frozen=True)
class ClientInfo:
    client_id: str
    client_name: str
    aum_usd: float


@dataclass(frozen=True)
class RmInfo:
    rm_id: str
    rm_name: str
    clients: tuple[ClientInfo, ...]


class OverviewSource(Protocol):
    """Swappable input."""

    def location(self, as_of: date) -> str: ...
    def has_actions(self, as_of: date) -> bool: ...
    def client_actions(self, as_of: date, client_id: str) -> ClientActions | None: ...
    def findings(self, as_of: date, client_id: str) -> dict[str, FlatFinding] | None: ...
    def reconciliation(self, as_of: date, client_id: str) -> Reconciliation | None: ...
    def mandate_reconciliation(self, as_of: date, client_id: str) -> MandateReconciliation | None: ...


class StoreOverviewSource:
    """Reports, reconciliations and actions of a date as written by the earlier stages."""

    def __init__(self, store: ArtifactStore | str | Path):
        self.reports = StoreReportSource(store)
        self.store = self.reports.store

    def location(self, as_of: date) -> str:
        return self.reports.location(as_of)

    def has_actions(self, as_of: date) -> bool:
        return bool(self.store.keys(as_of, Kind.ACTIONS))

    def client_actions(self, as_of: date, client_id: str) -> ClientActions | None:
        return read_model(self.store, as_of, Kind.ACTIONS, client_id, ClientActions)

    def findings(self, as_of: date, client_id: str) -> dict[str, FlatFinding] | None:
        report = self.reports.report(as_of, client_id)
        return {f.ref: f for f in flatten(report)} if report else None

    def reconciliation(self, as_of: date, client_id: str) -> Reconciliation | None:
        return read_model(self.store, as_of, Kind.RECONCILIATION, client_id, Reconciliation)

    def mandate_reconciliation(self, as_of: date, client_id: str) -> MandateReconciliation | None:
        return read_model(self.store, as_of, Kind.MANDATE_RECONCILIATION, client_id, MandateReconciliation)


def rms_at(repo, as_of: date) -> dict[str, RmInfo]:
    """RMs with their clients at ``as_of``, ordered by RM id and client id."""
    rows = repo.clients(as_of=as_of).frame.iter_rows(named=True)
    by: dict[str, dict] = {}
    for r in rows:
        rm = by.setdefault(r["rm_id"], {"name": r["rm_name"], "clients": []})
        rm["clients"].append(ClientInfo(r["client_id"], r["client_name"], float(r["aum_usd"] or 0.0)))
    return {rid: RmInfo(rid, v["name"], tuple(sorted(v["clients"], key=lambda c: c.client_id))) for rid, v in sorted(by.items())}
