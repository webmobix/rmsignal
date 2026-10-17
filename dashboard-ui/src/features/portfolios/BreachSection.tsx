import type { Schemas } from "#/api/client";
import { IdLink } from "#/components/IdLink";
import { fmtDate, fmtPct } from "#/lib/format";
import { breachLabel } from "../clients/status";

type Detail = Schemas["PortfolioDetail"];

/** Exclusion breaches and the RM's notes about the portfolio's breaches. A note is a claim, never a pass. */
export function BreachSection({
	exclusions,
	reconciliation,
	embedded = false,
}: {
	exclusions: Detail["exclusion_breaches"];
	reconciliation: Detail["breach_reconciliation"];
	/** Inside another section: a small heading instead of a section of its own. */
	embedded?: boolean;
}) {
	const noted = reconciliation.filter((r) => r.status !== "no_note");
	if (!exclusions.length && !noted.length) return null;
	const byKey = new Map(reconciliation.map((r) => [`${r.kind}/${r.key}`, r]));
	return (
		<section className={embedded ? "mt-4" : "mt-10"} aria-labelledby="breach-h">
			{embedded ? (
				<h3
					id="breach-h"
					className="mb-2 text-xs font-semibold uppercase text-ink-muted"
				>
					Breaches and notes
				</h3>
			) : (
				<h2 id="breach-h" className="mb-3 text-xl">
					Breaches and notes
				</h2>
			)}
			{exclusions.length ? (
				<ul className="space-y-1" data-testid="exclusion-breaches">
					{exclusions.map((b) => {
						const label = breachLabel(
							byKey.get(`exclusion/${b.key}`) ?? {
								status: b.status,
								note_ids: b.note_ids,
							},
						);
						return (
							<li key={b.key} className="font-medium text-alert">
								Exclusion breach: <IdLink id={b.instrument_id} />{" "}
								{b.instrument_name} is{" "}
								<span className="num">{fmtPct(b.weight_pct)}</span> of the
								portfolio
								{b.held === "look_through"
									? `, held through ${b.via_instrument_name}`
									: ""}
								{label ? (
									<span className="font-normal text-ink-2"> · {label}</span>
								) : null}
							</li>
						);
					})}
				</ul>
			) : null}
			{noted.length ? (
				<ul className="mt-4 space-y-4" data-testid="breach-notes">
					{noted.map((r) => (
						<li key={`${r.kind}/${r.key}`}>
							<div className="font-medium text-alert">
								{r.description || r.key}
								<span className="font-normal text-ink-2">
									{" "}
									· {breachLabel(r)}
								</span>
							</div>
							{r.notes.map((n) => (
								<blockquote
									key={n.note_id}
									className="mt-1 border-l-2 border-rule pl-3 text-ink-2"
								>
									“{n.quote}”
									<footer className="text-ink-muted">
										RM note {n.note_id}, {fmtDate(n.note_date)}
									</footer>
								</blockquote>
							))}
							{r.waiver_claimed ? (
								<p className="mt-1 text-ink-muted">
									The waiver is the RM's statement and is not verified; it is a
									claim to verify. The breach stays flagged.
								</p>
							) : null}
						</li>
					))}
				</ul>
			) : null}
		</section>
	);
}
