"""Polars implementation of ``PitRepository`` over the seeded SQLite mirror.

This module is the only consumer of the ``DataSource`` contract for analysis code. Tables are
loaded once into Polars frames; wide per-date column groups are melted into long tables.
"""

import dataclasses
import re
from datetime import date

import polars as pl

from rm_dashboard.data.contract import DataSource
from rm_dashboard.domain import QualityFlag, Source

from .config import QualityConfig
from .repository import AsOfError, PitResult, Resolution

_DATE_SUFFIX = re.compile(r"^(?P<measure>.+)_(?P<y>\d{4})_(?P<m>\d{2})_(?P<d>\d{2})$")

CLIENT_CURRENT_ONLY = [
    "risk_profile", "risk_tolerance_score", "investment_horizon_years", "liquidity_needs",
    "objectives", "kyc_review_due", "pep_status", "tax_domicile", "country_of_residence",
    "wealth_band", "base_currency", "life_stage", "source_of_wealth",
]
PORTFOLIO_CURRENT_ONLY = ["mandate_code", "mandate_name", "service_model", "benchmark", "base_currency"]
INSTRUMENT_CURRENT_ONLY = [
    "asset_class", "sub_asset_class", "sector", "region", "liquidity_tier",
    "underlying_reference", "sustainability_excluded", "concentration_limit_applies",
]
ASSUMED_KNOWN_FLAG = "assumed_known_since_relationship_start"
MANDATE_CURRENT_ONLY = ["min_pct", "target_pct", "max_pct", "max_single_position_pct", "mandate_notes"]


def _require(as_of) -> date:
    if type(as_of) is not date:
        raise AsOfError(f"as_of must be a datetime.date, got {as_of!r}")
    return as_of


def _frame(rows: list, schema_hint: type | None = None) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame()
    return pl.DataFrame([dataclasses.asdict(r) for r in rows], infer_schema_length=None)


def _long(rows: list, id_cols: list[str], measures: dict[str, str]) -> pl.DataFrame:
    """Melt ``<measure>_YYYY_MM_DD`` columns into one row per entity and snapshot date."""
    out = []
    for r in rows:
        d = dataclasses.asdict(r)
        by_date: dict[date, dict] = {}
        for name, value in d.items():
            m = _DATE_SUFFIX.match(name)
            if m and m["measure"] in measures:
                snap = date(int(m["y"]), int(m["m"]), int(m["d"]))
                by_date.setdefault(snap, {})[measures[m["measure"]]] = value
        for snap, vals in by_date.items():
            out.append({**{c: d[c] for c in id_cols}, "snapshot_date": snap, **vals})
    return pl.DataFrame(out, infer_schema_length=None).sort([*id_cols, "snapshot_date"])


class PolarsPitRepository:
    def __init__(self, ds: DataSource, config: QualityConfig | None = None):
        self.config = config or QualityConfig()
        self._clients = _frame(ds.list_clients())
        self._portfolios = _frame(ds.list_portfolios())
        self._holdings = _frame(ds.list_holdings())
        self._instruments = _frame(ds.list_instruments())
        self._mandates = _frame(ds.list_mandates())
        self._transactions = _frame(ds.list_transactions())
        self._facilities = _frame(ds.list_credit_facilities())
        self._commitments = _frame(ds.list_commitments())
        self._cash_needs = _frame(ds.list_planned_cash_needs())
        self._market = _frame(ds.list_market_context())
        self._events = _frame(ds.list_events())
        self._notes = _frame(ds.list_rm_notes())

        self._aum = _long(ds.list_portfolios(), ["portfolio_id"], {"aum": "aum"})
        self._prices = _long(ds.list_instruments(), ["instrument_id"], {"price": "price"})
        self._fac_long = _long(
            ds.list_credit_facilities(), ["facility_id", "client_id", "collateral_portfolio_id"],
            {"drawn": "drawn", "collateral_market_value": "collateral_market_value",
             "lending_value": "lending_value", "ltv_pct": "ltv_pct", "headroom": "headroom"},
        )
        self._snapshots = sorted(self._holdings["snapshot_date"].unique().to_list())

    # ---- resolution -------------------------------------------------------------
    def snapshot_dates(self) -> list[date]:
        return list(self._snapshots)

    def resolve(self, *, as_of: date) -> Resolution:
        as_of = _require(as_of)
        eligible = [s for s in self._snapshots if s <= as_of]
        if not eligible:
            return Resolution(
                as_of, None, None, "insufficient_data",
                f"as_of {as_of} is before the first snapshot {self._snapshots[0]}",
            )
        eff = eligible[-1]
        return Resolution(as_of, eff, (as_of - eff).days)

    def _snapshot_result(self, dataset: str, as_of: date, build, pit: str = "snapshot") -> PitResult:
        """Wrap a frame builder that takes the effective snapshot date."""
        res = self.resolve(as_of=as_of)
        if res.status != "ok":
            return PitResult(pl.DataFrame(), as_of, dataset, None, None, res.status, res.reason, pit)
        frame = build(res.effective_snapshot_date)
        flags: list[QualityFlag] = []
        if res.gap_days is not None and res.gap_days > self.config.snapshot_gap_flag_days:
            flags.append(QualityFlag(
                code="snapshot_lag",
                message=f"as_of {as_of} resolved to snapshot {res.effective_snapshot_date} "
                        f"({res.gap_days} days earlier)",
            ))
        return PitResult(
            frame, as_of, dataset, res.effective_snapshot_date, res.gap_days, "ok", None, pit, [], flags,
        )

    @staticmethod
    def _sources(result: PitResult, key_cols: list[str], snapshot_col: str | None = "snapshot_date") -> PitResult:
        f = result.frame
        if f.is_empty():
            return result
        snaps = f[snapshot_col].to_list() if snapshot_col and snapshot_col in f.columns else [None] * f.height
        keys = ["/".join(str(v) for v in row) for row in f.select(key_cols).iter_rows()]
        result.sources = [Source(dataset=result.dataset, key=k, snapshot_date=s) for k, s in zip(keys, snaps)]
        return result

    # ---- unversioned (current_only) ---------------------------------------------
    def clients(self, *, as_of: date, client_id: str | None = None) -> PitResult:
        as_of = _require(as_of)
        f = self._clients
        if client_id:
            f = f.filter(pl.col("client_id") == client_id)
        flags = []
        status, reason = "ok", None
        # total_aum_usd in the source is the *current* total: a dated quantity must not leak into a historical
        # as_of, so it is dropped and recomputed from the holdings of the effective snapshot.
        res = self.resolve(as_of=as_of)
        f = f.drop("total_aum_usd")
        if res.status == "ok":
            tot = (self._holdings.filter(pl.col("snapshot_date") == res.effective_snapshot_date)
                   .group_by("client_id").agg(pl.col("market_value_usd").sum().alias("aum_usd")))
            f = f.join(tot, on="client_id", how="left").with_columns(
                pl.lit(res.effective_snapshot_date).alias("aum_snapshot_date"))
        else:
            f = f.with_columns(pl.lit(None, dtype=pl.Float64).alias("aum_usd"), pl.lit(None, dtype=pl.Date).alias("aum_snapshot_date"))
        if f.height:
            f = f.with_columns(
                (pl.col("kyc_review_due") < as_of).alias("kyc_overdue"),
                (pl.col("kyc_review_due") - as_of).dt.total_days().alias("days_to_kyc_due"),
            )
            before = f.filter(pl.col("client_since") > as_of)
            f = f.filter(pl.col("client_since") <= as_of)
            if before.height and not f.height:
                status, reason = "insufficient_data", f"client relationship starts after as_of {as_of}"
        r = PitResult(
            f, as_of, "clients", None, None, status, reason, "current_only",
            list(CLIENT_CURRENT_ONLY), flags,
        )
        if f.height and as_of < date.max:
            r.flags.append(QualityFlag(
                code="current_only",
                message="client attributes have no history: values are as currently held, "
                        f"not as at {as_of}",
            ))
        return self._sources(r, ["client_id"], None)

    def portfolios(self, *, as_of: date, client_id: str | None = None, portfolio_id: str | None = None) -> PitResult:
        as_of = _require(as_of)
        f = self._portfolios.select(
            "portfolio_id", "client_id", "portfolio_name", "mandate_code", "mandate_name",
            "service_model", "base_currency", "inception_date", "benchmark",
        )
        if client_id:
            f = f.filter(pl.col("client_id") == client_id)
        if portfolio_id:
            f = f.filter(pl.col("portfolio_id") == portfolio_id)
        f = f.filter(pl.col("inception_date") <= as_of)
        res = self.resolve(as_of=as_of)
        if res.status == "ok":
            aum = self._aum.filter(pl.col("snapshot_date") == res.effective_snapshot_date).select(
                "portfolio_id", pl.col("aum")
            )
            f = f.join(aum, on="portfolio_id", how="left")
        r = PitResult(
            f, as_of, "portfolios", res.effective_snapshot_date, res.gap_days, "ok", None,
            "current_only", list(PORTFOLIO_CURRENT_ONLY),
        )
        if res.status != "ok":
            r.status, r.reason = res.status, res.reason
        r.flags.append(QualityFlag(
            code="current_only",
            message="mandate, service model and benchmark have no history: values are as currently held",
        ))
        return self._sources(r, ["portfolio_id"], None)

    def mandates(self, *, as_of: date, mandate_code: str | None = None) -> PitResult:
        as_of = _require(as_of)
        f = self._mandates
        if mandate_code:
            f = f.filter(pl.col("mandate_code") == mandate_code)
        r = PitResult(f, as_of, "mandates", None, None, "ok", None, "current_only", list(MANDATE_CURRENT_ONLY))
        r.flags.append(QualityFlag(code="current_only", message="mandate bands have no history: values are as currently held"))
        return self._sources(r, ["mandate_code", "asset_class"], None)

    def instruments(self, *, as_of: date, instrument_ids: list[str] | None = None) -> PitResult:
        as_of = _require(as_of)
        f = self._instruments.select(
            "instrument_id", "instrument_name", "asset_class", "sub_asset_class", "sector", "region",
            "currency", "liquidity_tier", "underlying_reference", "sustainability_excluded",
            "concentration_limit_applies",
        )
        if instrument_ids is not None:
            f = f.filter(pl.col("instrument_id").is_in(instrument_ids))
        r = PitResult(f, as_of, "instruments", None, None, "ok", None, "current_only", list(INSTRUMENT_CURRENT_ONLY))
        r.flags.append(QualityFlag(code="current_only", message="instrument classification has no history: values are as currently held"))
        return self._sources(r, ["instrument_id"], None)

    # ---- snapshot-dated ----------------------------------------------------------
    def holdings(self, *, as_of: date, client_id: str | None = None, portfolio_id: str | None = None) -> PitResult:
        as_of = _require(as_of)

        def build(eff: date) -> pl.DataFrame:
            f = self._holdings.filter(pl.col("snapshot_date") == eff)
            if client_id:
                f = f.filter(pl.col("client_id") == client_id)
            if portfolio_id:
                f = f.filter(pl.col("portfolio_id") == portfolio_id)
            return f

        r = self._snapshot_result("holdings", as_of, build)
        if r.status == "ok":
            r.flags.extend(self._holding_flags(r.frame, r.effective_snapshot_date))
        return self._sources(r, ["portfolio_id", "instrument_id"])

    def _holding_flags(self, f: pl.DataFrame, eff: date) -> list[QualityFlag]:
        cfg, flags = self.config, []
        for row in f.iter_rows(named=True):
            subj = f"{row['portfolio_id']}/{row['instrument_id']}"
            lag = (row["snapshot_date"] - row["valuation_date"]).days
            if lag > cfg.stale_mark_days:
                flags.append(QualityFlag(
                    code="stale_mark", subject=subj,
                    message=f"valuation_date {row['valuation_date']} is earlier than snapshot_date "
                            f"{row['snapshot_date']} ({lag} days)",
                ))
            if row["cost_basis_base"] is None:
                flags.append(QualityFlag(
                    code="missing_cost_basis", subject=subj,
                    message="no cost basis: position excluded from profit and loss figures",
                ))
        prior = [s for s in self._snapshots if s < eff]
        if prior and f.height:
            prev = self._holdings.filter(pl.col("snapshot_date") == prior[-1])
            have = {(p, i) for p, i in prev.select("portfolio_id", "instrument_id").iter_rows()}
            for row in f.iter_rows(named=True):
                if (row["portfolio_id"], row["instrument_id"]) not in have:
                    # a portfolio that had no prior positions at all is simply new, not mid-period
                    if any(p == row["portfolio_id"] for p, _ in have):
                        flags.append(QualityFlag(
                            code="mid_period_position", subject=f"{row['portfolio_id']}/{row['instrument_id']}",
                            message=f"position first appears at {eff}, absent at {prior[-1]} "
                                    f"(acquired {row['acquired_date']}): period change includes flow",
                        ))
        bonds = f.filter(pl.col("asset_class").is_in(list(cfg.bond_asset_classes)))
        if bonds.height:
            flags.append(QualityFlag(
                code="bond_nominal_unit", subject=f"{bonds.height} positions",
                message=f"bond quantity is in units of {cfg.bond_nominal_unit} nominal; "
                        "market value is quantity x price",
            ))
        return flags

    def instrument_prices(self, *, as_of: date, instrument_id: str | None = None) -> PitResult:
        as_of = _require(as_of)
        res = self.resolve(as_of=as_of)
        if res.status != "ok":
            return PitResult(pl.DataFrame(), as_of, "instrument_price", None, None, res.status, res.reason)
        f = self._prices.filter(pl.col("snapshot_date") <= res.effective_snapshot_date)
        if instrument_id:
            f = f.filter(pl.col("instrument_id") == instrument_id)
        r = PitResult(f, as_of, "instrument_price", res.effective_snapshot_date, res.gap_days)
        return self._sources(r, ["instrument_id"])

    def portfolio_aum(self, *, as_of: date, portfolio_id: str | None = None) -> PitResult:
        as_of = _require(as_of)
        res = self.resolve(as_of=as_of)
        if res.status != "ok":
            return PitResult(pl.DataFrame(), as_of, "portfolio_aum", None, None, res.status, res.reason)
        f = self._aum.filter(pl.col("snapshot_date") <= res.effective_snapshot_date)
        if portfolio_id:
            f = f.filter(pl.col("portfolio_id") == portfolio_id)
        r = PitResult(f, as_of, "portfolio_aum", res.effective_snapshot_date, res.gap_days)
        return self._sources(r, ["portfolio_id"])

    def facility_snapshots(self, *, as_of: date, client_id: str | None = None, facility_id: str | None = None) -> PitResult:
        as_of = _require(as_of)
        res = self.resolve(as_of=as_of)
        if res.status != "ok":
            return PitResult(pl.DataFrame(), as_of, "facility_snapshot", None, None, res.status, res.reason)
        f = self._fac_long.filter(pl.col("snapshot_date") <= res.effective_snapshot_date)
        if client_id:
            f = f.filter(pl.col("client_id") == client_id)
        if facility_id:
            f = f.filter(pl.col("facility_id") == facility_id)
        r = PitResult(f, as_of, "facility_snapshot", res.effective_snapshot_date, res.gap_days)
        r.flags.extend(self._drawdown_flags(f, as_of))
        return self._sources(r, ["facility_id"])

    def facility_terms(self, *, as_of: date, client_id: str | None = None, facility_id: str | None = None) -> PitResult:
        """Facility terms (limit, trigger, currency); unversioned, hence current_only."""
        as_of = _require(as_of)
        f = self._facilities.select(
            "facility_id", "client_id", "collateral_portfolio_id", "facility_type", "facility_ccy",
            "credit_limit", "interest_rate_pct", "margin_call_ltv_pct")
        if client_id:
            f = f.filter(pl.col("client_id") == client_id)
        if facility_id:
            f = f.filter(pl.col("facility_id") == facility_id)
        r = PitResult(f, as_of, "credit_facilities", None, None, "ok", None, "current_only",
                      ["credit_limit", "interest_rate_pct", "margin_call_ltv_pct"])
        r.flags.append(QualityFlag(code="current_only", message="facility terms have no history: values are as currently held"))
        return self._sources(r, ["facility_id"], None)

    def _drawdown_flags(self, f: pl.DataFrame, as_of: date) -> list[QualityFlag]:
        cfg, flags = self.config, []
        tx = self._transactions.filter(
            pl.col("transaction_type").is_in(list(cfg.drawdown_types)) & (pl.col("trade_date") <= as_of)
        )
        for fid in f["facility_id"].unique().sort().to_list():
            fac = f.filter(pl.col("facility_id") == fid).sort("snapshot_date")
            pf = fac["collateral_portfolio_id"][0]
            snaps, drawn = fac["snapshot_date"].to_list(), fac["drawn"].to_list()
            for i in range(1, len(snaps)):
                delta = drawn[i] - drawn[i - 1]
                if delta <= 0:
                    continue
                booked = tx.filter(
                    (pl.col("portfolio_id") == pf)
                    & (pl.col("trade_date") > snaps[i - 1]) & (pl.col("trade_date") <= snaps[i])
                )["amount"].sum()
                if abs(delta - booked) > cfg.drawdown_tolerance:
                    flags.append(QualityFlag(
                        code="facility_drawdown_mismatch", subject=fid,
                        message=f"drawn rose by {delta:,.0f} between {snaps[i - 1]} and {snaps[i]} "
                                f"but drawdown transactions total {booked:,.0f}",
                    ))
        return flags

    def market_context(self, *, as_of: date, series_id: str | None = None) -> PitResult:
        as_of = _require(as_of)

        def build(eff: date) -> pl.DataFrame:
            f = self._market.filter(pl.col("snapshot_date") == eff)
            return f.filter(pl.col("series_id") == series_id) if series_id else f

        r = self._snapshot_result("market_context", as_of, build)
        return self._sources(r, ["series_id"])

    def market_history(self, *, as_of: date) -> PitResult:
        """Every market snapshot up to the effective one, oldest first."""
        as_of = _require(as_of)
        r = self._snapshot_result("market_history", as_of, lambda eff: self._market.filter(pl.col("snapshot_date") <= eff)
                                  .sort("snapshot_date", "series_id"))
        return self._sources(r, ["series_id"])

    # ---- event-dated -------------------------------------------------------------
    def _event_result(self, dataset: str, frame: pl.DataFrame, date_col: str, as_of: date,
                      key_cols: list[str]) -> PitResult:
        f = frame.filter(pl.col(date_col) <= as_of) if frame.height else frame
        r = PitResult(f, as_of, dataset, None, None, "ok", None, "event")
        return self._sources(r, key_cols, None)

    def transactions(self, *, as_of: date, client_id: str | None = None, portfolio_id: str | None = None) -> PitResult:
        as_of = _require(as_of)
        f = self._transactions
        if client_id:
            f = f.filter(pl.col("client_id") == client_id)
        if portfolio_id:
            f = f.filter(pl.col("portfolio_id") == portfolio_id)
        r = self._event_result("transactions", f, "trade_date", as_of, ["transaction_id"])
        if r.frame.height:
            pf_ccy = dict(self._portfolios.select("portfolio_id", "base_currency").iter_rows())
            for row in r.frame.iter_rows(named=True):
                if (row["transaction_type"] in self.config.subscription_types
                        and row["currency"] != pf_ccy.get(row["portfolio_id"])):
                    r.flags.append(QualityFlag(
                        code="subscription_currency_mismatch", subject=row["transaction_id"],
                        message=f"subscription settled in {row['currency']} but portfolio "
                                f"{row['portfolio_id']} base currency is {pf_ccy.get(row['portfolio_id'])}",
                    ))
        return r

    def events(self, *, as_of: date) -> PitResult:
        as_of = _require(as_of)
        return self._event_result("event_log", self._events, "event_date", as_of, ["event_date", "event_type"])

    def notes(self, *, as_of: date, client_id: str | None = None) -> PitResult:
        as_of = _require(as_of)
        f = self._notes
        if client_id:
            f = f.filter(pl.col("client_id") == client_id)
        return self._event_result("rm_notes", f, "note_date", as_of, ["note_id"])

    def _known_since_relationship(self, frame: pl.DataFrame, as_of: date, client_id: str | None) -> pl.DataFrame:
        """Rows without a knowledge date are assumed known since the client relationship began."""
        if client_id:
            frame = frame.filter(pl.col("client_id") == client_id)
        if frame.is_empty():
            return frame
        since = self._clients.select("client_id", "client_since")
        return frame.join(since, on="client_id", how="left").filter(pl.col("client_since") <= as_of).drop("client_since")

    def cash_needs(self, *, as_of: date, client_id: str | None = None) -> PitResult:
        """Planned needs carry no knowledge date, only a future due window.

        Rule: a need with no recorded creation date is assumed to have existed since the start of the
        client relationship, so it is available from ``client_since`` onwards and never dropped after.
        """
        as_of = _require(as_of)
        f = self._known_since_relationship(self._cash_needs, as_of, client_id)
        r = PitResult(f, as_of, "planned_cash_needs", None, None, "ok", None, "current_only")
        r.flags.append(QualityFlag(
            code=ASSUMED_KNOWN_FLAG,
            message="planned needs have no recorded creation date: assumed known since the start of the client relationship",
        ))
        return self._sources(r, ["need_id"], None)

    def commitments(self, *, as_of: date, client_id: str | None = None) -> PitResult:
        """Commitments show today's uncalled amount; same assumption as planned needs."""
        as_of = _require(as_of)
        f = self._known_since_relationship(self._commitments, as_of, client_id)
        r = PitResult(f, as_of, "commitments", None, None, "ok", None, "current_only")
        r.flags.append(QualityFlag(
            code=ASSUMED_KNOWN_FLAG,
            message="commitments have no history (uncalled amount is today's): assumed in place since the start of the client relationship",
        ))
        return self._sources(r, ["commitment_id"], None)
