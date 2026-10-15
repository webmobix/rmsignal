"""
Tax-aware optimisation, gated on domicile.

The naive version pairs unrealised losses with gains and calls it harvesting.
On this book that is wrong for eight of twenty clients, because their tax
domicile levies no capital gains tax at all. Stating the non-recommendation is
worth more than making the recommendation.
"""
from schema import Finding
import severity as sv
from severity import Sev
import notes as notes_mod

NO_CGT = {"Hong Kong SAR", "Singapore", "United Arab Emirates"}


def run(book, claims):
    out = []
    for client in book.clients:
        cid = client["client_id"]
        domicile = client["tax_domicile"]
        wealth = book.wealth(cid)
        gains = losses = 0.0
        worst = []
        for iid, pos in book.positions(cid).items():
            if pos["pnl"] > 0:
                gains += pos["pnl"]
            else:
                losses += pos["pnl"]
                worst.append({"instrument": book.I[iid]["instrument_name"],
                              "unrealised_usd": round(pos["pnl"]),
                              "market_value_usd": round(pos["mv"])})
        if losses > -500_000:
            continue
        worst.sort(key=lambda x: x["unrealised_usd"])
        cgt = domicile not in NO_CGT
        offshore = client["country_of_residence"] != domicile

        if cgt:
            sev = Sev.of("USD %.1fm of losses against USD %.1fm of wealth" % (
                             abs(losses) / 1e6, wealth / 1e6),
                         "losses / wealth x %g" % sv.TAX_LOSS_SCALE,
                         abs(losses) / wealth * sv.TAX_LOSS_SCALE).cap(sv.TAX_CEILING)
            headline = "USD %.1fm of losses can be set against USD %.1fm of gains" % (
                abs(losses) / 1e6, gains / 1e6)
            detail = ("Tax domicile is %s%s. USD %.1fm of unrealised losses sit alongside "
                      "USD %.1fm of unrealised gains — the largest loss is %s at USD %.1fm." % (
                          domicile,
                          " while resident in %s" % client["country_of_residence"] if offshore else "",
                          abs(losses) / 1e6, gains / 1e6,
                          worst[0]["instrument"], abs(worst[0]["unrealised_usd"]) / 1e6))
            action = ("Model the offset with wealth planning before trading, and check the "
                      "repurchase would not be treated as a wash sale.")
        else:
            sev = Sev.of("tax domicile %s levies no capital gains tax" % domicile,
                         "a non-recommendation, not an action", sv.TAX_NO_CGT)
            headline = "Loss harvesting is not an action for this client"
            detail = ("USD %.1fm of unrealised losses — among the largest in the book — but the "
                      "tax domicile is %s, which levies no capital gains tax. Crystallising the "
                      "loss buys nothing. If the position should be sold, it should be sold on "
                      "its merits, and there is no tax reason not to." % (abs(losses) / 1e6, domicile))
            action = ("Say this explicitly. The client may believe he is protecting something "
                      "by not selling.")

        out.append(Finding(
            id="TAX-%s" % cid, client_id=cid, dimension="tax", severity=sev,
            headline=headline, detail=detail, action=action,
            rule_text=("gate on clients.tax_domicile, never country_of_residence — they differ "
                       "for 7 of 20 clients; Hong Kong SAR, Singapore and the UAE levy no "
                       "capital gains tax, so harvesting is reported as a non-recommendation; "
                       "severity = losses / wealth x %g" % sv.TAX_LOSS_SCALE),
            numbers={"gains_usd": round(gains), "losses_usd": round(losses),
                     "domicile": domicile, "residence": client["country_of_residence"],
                     "cgt_regime": cgt, "largest": worst[:4]},
            source_rows=["clients.%s" % cid, "holdings.%s.%s" % (cid, book.today)],
            confidence="medium",
            check=("Domicile drives this entirely and the dataset records one value. "
                   "Confirm current domicile and any treaty position with wealth planning."),
            evidence=notes_mod.has(claims, cid, "escalate", "refusal")))
    return out
