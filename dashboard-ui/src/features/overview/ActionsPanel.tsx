import { useState } from "react";
import type { Overview } from "#/api/queries";
import { titleCase } from "#/lib/format";
import { TIER_COLOR, TIER_LABEL, TIERS } from "#/lib/tiers";
import { ActionTable } from "./ActionList";
import { DATA_QUALITY, splitActions, tierCounts } from "./actions";

export function TierFilter({
	counts,
	value,
	onChange,
}: {
	counts: Record<string, number>;
	value: string | null;
	onChange: (tier: string | null) => void;
}) {
	return (
		<fieldset
			className="m-0 flex min-w-0 flex-wrap items-center gap-x-5 gap-y-2 border-0 p-0"
			aria-label="Filter by importance"
		>
			{TIERS.filter((t) => counts[t]).map((tier) => {
				const on = value === tier;
				const dim = value !== null && !on;
				return (
					<button
						key={tier}
						type="button"
						aria-pressed={on}
						onClick={() => onChange(on ? null : tier)}
						className={`flex items-center gap-2 text-[13px] ${dim ? "opacity-50" : ""} ${on ? "font-semibold text-navy-950 shadow-[inset_0_-1px_0_0_var(--color-navy-950)]" : "text-ink-2"}`}
					>
						<span
							className="size-2 rounded-full"
							style={{ background: TIER_COLOR[tier] }}
						/>
						<span className="num font-serif text-[22px] leading-none text-navy-950">
							{counts[tier]}
						</span>
						{TIER_LABEL[tier]}
					</button>
				);
			})}
		</fieldset>
	);
}

export function ActionsPanel({ overview }: { overview: Overview }) {
	const [tier, setTier] = useState<string | null>(null);
	const [category, setCategory] = useState<string | null>(null);
	const { risks, dataQuality } = splitActions(overview.actions, {
		tier,
		category,
	});
	const categories = overview.by_category.filter(
		(c) => c.category !== DATA_QUALITY,
	);
	return (
		<section aria-labelledby="actions-h" className="mt-10">
			<div className="flex flex-wrap items-end justify-between gap-4">
				<h2 id="actions-h" className="text-[26px]">
					Next actions
				</h2>
				<TierFilter
					counts={tierCounts(overview.actions)}
					value={tier}
					onChange={setTier}
				/>
			</div>
			<fieldset
				className="m-0 mt-3 flex min-w-0 flex-wrap gap-2 border-0 p-0"
				aria-label="Filter by category"
			>
				{categories.map((c) => {
					const on = category === c.category;
					return (
						<button
							key={c.category}
							type="button"
							aria-pressed={on}
							onClick={() => setCategory(on ? null : c.category)}
							className={`border px-2.5 py-1 text-xs ${on ? "border-navy-950 bg-navy-950 text-canvas" : "border-rule bg-surface text-ink-2 hover:border-slate-blue"}`}
						>
							{titleCase(c.category)}{" "}
							<span className="num opacity-70">{c.count}</span>
						</button>
					);
				})}
			</fieldset>
			<div className="mt-4" data-testid="risk-actions">
				<ActionTable actions={risks} />
			</div>
			<details className="mt-8 border-t border-rule pt-4" data-testid="dq-lane">
				<summary className="cursor-pointer text-[13px] font-semibold text-navy-950">
					Data quality and coverage{" "}
					<span className="num font-normal text-ink-muted">
						({dataQuality.length})
					</span>
				</summary>
				<p className="mt-2 max-w-[760px] text-xs text-ink-muted">
					Gaps in the analysis, such as clients whose report produced no
					actions. Kept apart so they do not crowd out client risks.
				</p>
				<div className="mt-3">
					<ActionTable actions={dataQuality} empty="No data-quality items." />
				</div>
			</details>
		</section>
	);
}
