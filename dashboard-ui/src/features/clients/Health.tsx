import type { Schemas } from "#/api/client";
import { OpenActionLink } from "#/components/IdLink";
import { fmtDate, fmtPct, fmtUsd } from "#/lib/format";

type Detail = Schemas["ClientDetail"];

export interface HealthItem {
	key: string;
	label: string;
	status: "ok" | "watch" | "alert";
	figure: string;
	category: string;
}

/** Five health dimensions with their headline figure, derived from the consolidated payload. */
export function healthItems(d: Detail): HealthItem[] {
	const c = d.consolidated;
	const top = [...c.look_through].sort((a, b) => b.share_pct - a.share_pct)[0];
	const out = d.portfolios.filter((p) => p.mandate_status === "out_of_band");
	const fac = c.facilities.reduce<
		Detail["consolidated"]["facilities"][number] | null
	>(
		(min, f) =>
			!min || (f.ltv_gap_pp ?? 99) < (min.ltv_gap_pp ?? 99) ? f : min,
		null,
	);
	const liq = c.liquidity;
	const gap = fac?.ltv_gap_pp ?? null;
	return [
		{
			key: "concentration",
			label: "Concentration",
			status:
				top && top.share_pct >= 25
					? "alert"
					: top && top.share_pct >= 15
						? "watch"
						: "ok",
			figure: top
				? `${top.name} ${fmtPct(top.share_pct)}`
				: "No look-through data",
			category: "concentration_risk",
		},
		{
			key: "mandate",
			label: "Mandate",
			status: out.length ? "alert" : "ok",
			figure: out.length
				? `${out.length} portfolio${out.length === 1 ? "" : "s"} out of band`
				: "Within mandate",
			category: "mandate_drift",
		},
		{
			key: "liquidity",
			label: "Liquidity",
			status: !liq
				? "ok"
				: (liq.shortfall_usd ?? 0) > 0
					? "alert"
					: (liq.coverage_ratio ?? 99) < 1.5
						? "watch"
						: "ok",
			figure: !liq
				? "No liquidity data"
				: (liq.shortfall_usd ?? 0) > 0
					? `Shortfall ${fmtUsd(liq.shortfall_usd)}`
					: liq.coverage_ratio == null
						? "No planned needs"
						: `Needs covered ${liq.coverage_ratio.toFixed(1)}x`,
			category: "liquidity_cash_needs",
		},
		{
			key: "credit",
			label: "Credit",
			status:
				gap === null ? "ok" : gap < 5 ? "alert" : gap < 15 ? "watch" : "ok",
			figure: fac
				? `LTV ${fmtPct(fac.current?.ltv_pct)} · ${gap === null ? "n/a" : gap.toFixed(1)}pp below trigger`
				: "No credit facility",
			category: "credit_collateral",
		},
		{
			key: "kyc",
			label: "KYC",
			status: d.profile.kyc_overdue ? "alert" : "ok",
			figure: d.profile.kyc_overdue
				? `Review overdue (${fmtDate(d.profile.kyc_review_due)})`
				: `Review due ${fmtDate(d.profile.kyc_review_due)}`,
			category: "compliance_kyc",
		},
	];
}

const TONE = {
	ok: "text-positive",
	watch: "text-caution",
	alert: "text-alert",
} as const;
const WORD = { ok: "OK", watch: "Watch", alert: "Act" } as const;

export function Health({ detail }: { detail: Detail }) {
	const items = healthItems(detail);
	return (
		<section aria-labelledby="health-h" className="mt-10">
			<h2 id="health-h" className="mb-3 text-[26px]">
				Portfolio health
			</h2>
			<ul className="grid gap-3 md:grid-cols-5" data-testid="health">
				{items.map((item) => {
					const action = detail.actions.find(
						(a) => a.category === item.category,
					);
					return (
						<li key={item.key} className="card p-3">
							<div className="eyebrow">{item.label}</div>
							<div
								className={`mt-1 text-sm font-semibold ${TONE[item.status]}`}
							>
								{WORD[item.status]}
							</div>
							<p className="mt-1 text-xs text-ink-2">{item.figure}</p>
							<p className="mt-2 text-xs">
								{action ? (
									<OpenActionLink id={action.action_id}>
										See evidence
									</OpenActionLink>
								) : (
									<span className="text-ink-muted">No linked finding</span>
								)}
							</p>
						</li>
					);
				})}
			</ul>
		</section>
	);
}
