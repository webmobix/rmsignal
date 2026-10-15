"""Where the overview reads from: the persisted per-client outputs of a date, and the RM's clients."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from rm_dashboard.actions.contracts import ClientActions
from rm_dashboard.reconciliation import Reconciliation
from rm_dashboard.reportsource import FlatFinding, FolderReportSource, flatten


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
    """Swappable input: a folder today, a store later."""

    def location(self, as_of: date) -> str: ...
    def has_actions_folder(self, as_of: date) -> bool: ...
    def client_actions(self, as_of: date, client_id: str) -> ClientActions | None: ...
    def findings(self, as_of: date, client_id: str) -> dict[str, FlatFinding] | None: ...
    def reconciliation(self, as_of: date, client_id: str) -> Reconciliation | None: ...


class FolderOverviewSource:
    """``reports/<as_of>/{<client>.json, reconciliation/, actions/}`` as written by the earlier stages."""

    def __init__(self, base_dir: str | Path):
        self.reports = FolderReportSource(base_dir)

    def location(self, as_of: date) -> str:
        return str(self.reports.run_dir(as_of) / "actions")

    def has_actions_folder(self, as_of: date) -> bool:
        return (self.reports.run_dir(as_of) / "actions").is_dir()

    def client_actions(self, as_of: date, client_id: str) -> ClientActions | None:
        p = self.reports.run_dir(as_of) / "actions" / f"{client_id}.json"
        return ClientActions.model_validate_json(p.read_text()) if p.is_file() else None

    def findings(self, as_of: date, client_id: str) -> dict[str, FlatFinding] | None:
        report = self.reports.report(as_of, client_id)
        return {f.ref: f for f in flatten(report)} if report else None

    def reconciliation(self, as_of: date, client_id: str) -> Reconciliation | None:
        p = self.reports.run_dir(as_of) / "reconciliation" / f"{client_id}.json"
        return Reconciliation.model_validate_json(p.read_text()) if p.is_file() else None


def rms_at(repo, as_of: date) -> dict[str, RmInfo]:
    """RMs with their clients at ``as_of``, ordered by RM id and client id."""
    rows = repo.clients(as_of=as_of).frame.iter_rows(named=True)
    by: dict[str, dict] = {}
    for r in rows:
        rm = by.setdefault(r["rm_id"], {"name": r["rm_name"], "clients": []})
        rm["clients"].append(ClientInfo(r["client_id"], r["client_name"], float(r["aum_usd"] or 0.0)))
    return {rid: RmInfo(rid, v["name"], tuple(sorted(v["clients"], key=lambda c: c.client_id))) for rid, v in sorted(by.items())}
