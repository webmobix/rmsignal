import { useState } from "react";
import { fmtPct, fmtUsd } from "#/lib/format";
import {
	barPosition,
	CASE_LABEL,
	CASE_ORDER,
	type CaseName,
	type Totals,
} from "./scenarios";

/** A figure's explainer: how it was derived, shown on request. */
export function Explainer({ label, text }: { label: string; text?: string }) {
	const [open, setOpen] = useState(false);
	if (!text) return null;
	return (
		<div className="mt-1">
			<button
				type="button"
				aria-expanded={open}
				aria-label={label}
				onClick={() => setOpen(!open)}
				className="text-xs text-navy-700 underline decoration-rule underline-offset-2 hover:text-navy-950"
			>
				How is this derived?
			</button>
			{open ? (
				<p className="mt-1 max-w-prose text-xs text-ink-2" role="note">
					{text}
				</p>
			) : null}
		</div>
	);
}

/**
 * The three cases together: a bar on one axis (zero marked) and a column per case.
 * Only the position along the bar carries the range; colour never encodes good or bad.
 */
export function CaseRange({
	cases,
	explainers,
}: {
	cases: Record<string, Totals | undefined>;
	explainers?: Record<string, string>;
}) {
	const values = CASE_ORDER.map((c) => cases[c]?.delta_pct ?? 0);
	const zero = barPosition(0, values);
	return (
		<div data-testid="case-range">
			<div
				className="relative mb-5 mt-2 h-6"
				role="img"
				aria-label={`Range of change from ${fmtPct(values[0], 1, true)} to ${fmtPct(values[2], 1, true)}`}
			>
				<div className="absolute inset-x-0 top-2.5 h-1 bg-surface-sunk" />
				<div
					className="absolute top-2.5 h-1 bg-slate-blue"
					style={{
						left: `${barPosition(Math.min(...values), values)}%`,
						width: `${barPosition(Math.max(...values), values) - barPosition(Math.min(...values), values)}%`,
					}}
				/>
				<div
					className="absolute top-0 h-6 w-px bg-ink-muted"
					style={{ left: `${zero}%` }}
					title="No change"
				/>
				{CASE_ORDER.map((c, i) => (
					<div
						key={c}
						className={`absolute top-1 h-4 w-4 -translate-x-1/2 border-2 border-navy-950 ${c === "likely" ? "bg-navy-950" : "bg-canvas"}`}
						style={{ left: `${barPosition(values[i] ?? 0, values)}%` }}
						title={`${CASE_LABEL[c]}: ${fmtPct(values[i], 1, true)}`}
					/>
				))}
			</div>
			<div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
				{CASE_ORDER.map((c: CaseName) => {
					const t = cases[c];
					if (!t) return null;
					return (
						<div key={c} data-testid={`case-${c}`}>
							<div className="eyebrow mb-1">{CASE_LABEL[c]}</div>
							<div className="metric-value num">
								{fmtPct(t.delta_pct, 1, true)}
							</div>
							<div className="mt-1 text-xs text-ink-2">
								{fmtUsd(t.delta_usd, false)} · {fmtUsd(t.before_usd)} to{" "}
								{fmtUsd(t.after_usd)}
							</div>
							<Explainer
								label={`Explain the ${c} change`}
								text={explainers?.[c]}
							/>
						</div>
					);
				})}
			</div>
		</div>
	);
}
