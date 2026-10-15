"""
Mandate and suitability governance.

Three tests, and then the part that makes this advisory rather than compliance:
every breach is classified as drift, client-directed, or waived, from the notes.
A waived breach is suppressed from the action list and shown as governed — a
tool that cries wolf on a breach the client signed for gets switched off.
"""
from schema import Finding
import severity as sv
from severity import Sev
import notes as notes_mod


def _aggregate(rows, key):
    out = {}
    for r in rows:
        out[key(r)] = out.get(key(r), 0.0) + r["_mv"]
    return out


def _classify(book, claims, client_id, asset_class):
    """(status, severity multiplier, what to call that multiplier, evidence)"""
    waivers = notes_mod.has(claims, client_id, "waiver")
    if waivers:
        return "waived", sv.WAIVED_X, "waived in writing", waivers[-1:]
    directed = notes_mod.has(claims, client_id, "directed")
    if directed:
        return "directed", sv.DIRECTED_X, "client-directed, on file", directed[-1:]
    return "open", 1.0, "", []


def run(book, claims):
    out = []
    for client in book.clients:
        cid = client["client_id"]
        for p in book.managed_portfolios(cid):          # custody is never measured
            pid, code = p["portfolio_id"], p["mandate_code"]
            rows = book.portfolio_rows(pid)
            total = sum(r["_mv"] for r in rows)
            if not total:
                continue
            discretionary = p["service_model"] == "Discretionary"

            # ── 1. asset class bands ──────────────────────────────────────
            mix = _aggregate(rows, lambda r: r["asset_class"])
            for asset, (lo, tgt, hi) in book.bands[code].items():
                w = 100 * mix.get(asset, 0.0) / total
                gap = max(w - hi, lo - w)
                if gap <= 0.05:
                    continue
                status, mult, mult_label, evid = _classify(book, claims, cid, asset)
                sev = (Sev.of("%.1fpp outside the %s band" % (gap, code),
                              "gap x %g per point" % sv.MANDATE_BAND_PER_PP,
                              gap * sv.MANDATE_BAND_PER_PP)
                       .times("discretionary mandate",
                              sv.DISCRETIONARY_X if discretionary else 1.0)
                       .times(mult_label or "advisory, client's own choice", mult)
                       .cap(sv.MANDATE_BAND_CEILING))
                direction = "above" if w > hi else "below"
                out.append(Finding(
                    id="MAN-%s-%s" % (pid, asset[:4].upper().replace(" ", "")),
                    client_id=cid, dimension="mandate", severity=sev,
                    headline="%s is %.1f points %s its %s band in %s" % (
                        asset, gap, direction, code, pid),
                    detail=("%s runs %.1f%% %s against a %.0f–%.0f%% band in the %s mandate "
                            "(%s). Target is %.0f%%." % (
                                pid, w, asset, lo, hi, p["mandate_name"],
                                p["service_model"].lower(), tgt)),
                    action=("Bank-side drift in a discretionary mandate — correct it."
                            if discretionary and status == "open" else
                            "Client-directed. Confirm the position is still intended and documented."
                            if status == "directed" else
                            "Waived in writing. No action; shown for the record."
                            if status == "waived" else
                            "Advisory portfolio. Raise at the next review."),
                    rule_text=("weight(asset_class) outside [min_pct, max_pct] from mandates.csv; "
                               "managed portfolios only, custody is excluded; "
                               "severity = gap_pp x %g, x%g if Discretionary" % (
                                   sv.MANDATE_BAND_PER_PP, sv.DISCRETIONARY_X)),
                    numbers={"weight_pct": round(w, 2), "min_pct": lo, "max_pct": hi,
                             "target_pct": tgt, "gap_pp": round(gap, 2)},
                    source_rows=["portfolios.%s" % pid, "mandates.%s.%s" % (code, asset)],
                    status=status, evidence=evid))

            # ── 2. single position limit ──────────────────────────────────
            limit = book.single_limit[code]
            singles = _aggregate(
                [r for r in rows if book.I[r["instrument_id"]]["concentration_limit_applies"] == "Y"],
                lambda r: r["instrument_id"])
            for iid, mv in singles.items():
                w = 100 * mv / total
                if w <= limit + 0.05:
                    continue
                status, mult, mult_label, evid = _classify(book, claims, cid, None)
                out.append(Finding(
                    id="LIM-%s-%s" % (pid, iid),
                    client_id=cid, dimension="mandate",
                    severity=(Sev.of("%.1fpp over a %.0f%% single-position cap" % (w - limit, limit),
                                     "excess x %g per point" % sv.LIMIT_PER_PP,
                                     (w - limit) * sv.LIMIT_PER_PP)
                              .times(mult_label or "not waived or directed", mult)
                              .cap(sv.LIMIT_CEILING)),
                    headline="%s is %.1f%% of %s against a %.0f%% single-position limit" % (
                        book.I[iid]["instrument_name"], w, pid, limit),
                    detail=("The %s mandate caps any single position at %.0f%%. %s sits at %.1f%%, "
                            "%.1f points over." % (p["mandate_name"], limit,
                                                   book.I[iid]["instrument_name"], w, w - limit)),
                    action="Trim to the limit or document why it stands.",
                    rule_text=("weight > max_single_position_pct, applied only where "
                               "instruments.concentration_limit_applies = Y — not to diversified "
                               "funds, sovereigns or deposits"),
                    numbers={"weight_pct": round(w, 2), "limit_pct": limit},
                    source_rows=["holdings.%s.%s" % (pid, iid), "mandates.%s" % code],
                    status=status, evidence=evid))

            # ── 3. binding exclusions ─────────────────────────────────────
            if "excl" in book.mandate_notes.get(code, "").lower() or code == "SUSBAL":
                for r in rows:
                    inst = book.I[r["instrument_id"]]
                    if inst["sustainability_excluded"] != "Y":
                        continue
                    w = 100 * r["_mv"] / total
                    evid = notes_mod.has(claims, cid, "awareness_gap", "protected")
                    out.append(Finding(
                        id="EXC-%s-%s" % (pid, r["instrument_id"]),
                        client_id=cid, dimension="mandate",
                        severity=Sev.of(
                            "an instrument on the mandate's own exclusion list",
                            "%s mandate" % p["service_model"].lower(),
                            sv.EXCLUSION_DISCRETIONARY if discretionary
                            else sv.EXCLUSION_ADVISORY),
                        headline="%s breaches the %s exclusion list" % (
                            inst["instrument_name"], p["mandate_name"]),
                        detail=("%s holds %s at %.1f%%. It is flagged "
                                "sustainability_excluded and the %s mandate carries binding "
                                "exclusions: %s" % (pid, inst["instrument_name"], w,
                                                    p["mandate_name"], book.mandate_notes[code])),
                        action=("Discretionary mandate — this is the bank's error, not the "
                                "client's. Exit and tell her before she finds it."
                                if discretionary else
                                "Advisory — raise with the client and document the decision."),
                        rule_text=("instruments.sustainability_excluded = Y inside a mandate whose "
                                   "mandate_notes carry binding exclusions"),
                        numbers={"weight_pct": round(w, 2)},
                        source_rows=["holdings.%s.%s" % (pid, r["instrument_id"]),
                                     "instruments.%s" % r["instrument_id"]],
                        status="open", evidence=evid))
    return out
