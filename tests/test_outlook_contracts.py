import pytest
from pydantic import ValidationError

from rm_dashboard.outlook import Change, MarketOutlook, OutlookInputs, Reason, View
from rm_dashboard.outlook.contracts import CATEGORY_SEGMENT, SEGMENTS


def view(**kw):
    base = dict(segment="equity", direction="positive", confidence="medium",
                drivers=[Reason(claim="Equities rose.", evidence_ids=["ev_1"])], change=Change(kind="new"))
    return View(**{**base, **kw})


def test_round_trip():
    o = MarketOutlook(as_of="2026-08-26", status="complete", views=[view()], inputs=OutlookInputs(event_count=3))
    assert MarketOutlook.model_validate_json(o.model_dump_json()) == o


@pytest.mark.parametrize("field,value", [("segment", "crypto"), ("direction", "bullish"), ("horizon", "2y"), ("confidence", "certain")])
def test_closed_sets_reject_other_values(field, value):
    with pytest.raises(ValidationError):
        view(**{field: value})


def test_view_needs_a_driver_and_reason_needs_evidence():
    with pytest.raises(ValidationError):
        view(drivers=[])
    with pytest.raises(ValidationError):
        Reason(claim="x", evidence_ids=[])


def test_no_numeric_forecast_field():
    names = set(View.model_fields) | set(MarketOutlook.model_fields)
    assert not {n for n in names if any(k in n for k in ("target", "forecast", "price", "level"))}


def test_segments_cover_market_categories():
    assert set(CATEGORY_SEGMENT.values()) | {"overall"} == set(SEGMENTS)


# ---- instrument outlook ---------------------------------------------------------------------
from rm_dashboard.outlook import InstrumentInputs, InstrumentOutlook, InstrumentRef, InstrumentView, MarketContext, PricePoint


def instrument_view(**kw):
    base = dict(direction="positive", confidence="low", drivers=[Reason(claim="Price rose.", evidence_ids=["ev_1"])],
                change=Change(kind="new"))
    return InstrumentView(**{**base, **kw})


def test_instrument_outlook_round_trip():
    o = InstrumentOutlook(
        subject="SYN-EQ-0001", as_of="2026-08-26", status="complete", view=instrument_view(),
        instrument=InstrumentRef(instrument_id="SYN-EQ-0001", instrument_name="Fund", asset_class="Equity", sub_asset_class="DM"),
        price_path=[PricePoint(snapshot_date="2026-06-30", price=234.2)],
        market_context=[MarketContext(segment="equity", direction="positive", horizon="3m", confidence="medium")],
        inputs=InstrumentInputs(price_snapshot_date="2026-08-26", relevant_event_ids=["EVT-2026-03-04-1"]))
    assert InstrumentOutlook.model_validate_json(o.model_dump_json()) == o


@pytest.mark.parametrize("field,value", [("direction", "bullish"), ("horizon", "2y"), ("confidence", "certain")])
def test_instrument_view_closed_sets(field, value):
    with pytest.raises(ValidationError):
        instrument_view(**{field: value})


def test_instrument_view_needs_a_driver():
    with pytest.raises(ValidationError):
        instrument_view(drivers=[])


def test_instrument_outlook_holds_no_client_data():
    names = set(InstrumentOutlook.model_fields) | set(InstrumentView.model_fields) | set(InstrumentRef.model_fields)
    assert not {n for n in names if any(k in n for k in ("client", "portfolio", "quantity", "position", "target", "forecast"))}


def test_market_view_still_has_its_segment_and_shared_fields():
    v = view()
    assert v.segment == "equity" and v.direction == "positive" and v.change.kind == "new"
