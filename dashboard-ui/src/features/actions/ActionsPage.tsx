import { getRouteApi } from "@tanstack/react-router";
import { useState } from "react";
import type { Overview } from "#/api/queries";
import { useData } from "#/api/queries";
import { PageHeader } from "#/components/PageHeader";
import { StateBoundary } from "#/components/StateBoundary";
import { ActionTable } from "#/features/overview/ActionList";
import { TierFilter } from "#/features/overview/ActionsPanel";
import {
	DATA_QUALITY,
	splitActions,
	tierCounts,
} from "#/features/overview/actions";
import { titleCase } from "#/lib/format";

const HORIZONS = [
	"immediate",
	"within_30_days",
	"within_90_days",
	"later",
] as const;

const chip = (on: boolean) =>
	`border px-2.5 py-1 text-xs ${on ? "border-navy-950 bg-navy-950 text-canvas" : "border-rule bg-surface text-ink-2 hover:border-slate-blue"}`;

export function ActionsView({
	overview,
	tier,
	onTier,
}: {
	overview: Overview;
	tier: string | null;
	onTier: (tier: string | null) => void;
}) {
	const [category, setCategory] = useState<string | null>(null);
	const [horizon, setHorizon] = useState<string | null>(null);
	const { risks, dataQuality } = splitActions(overview.actions, {
		tier,
		category,
		horizon,
	});
	const categories = overview.by_category.filter(
		(c) => c.category !== DATA_QUALITY,
	);
	return (
		<>
			<div className="flex flex-wrap items-end justify-between gap-4">
				<h2 className="text-[26px]">All actions</h2>
				<TierFilter
					counts={tierCounts(overview.actions)}
					value={tier}
					onChange={onTier}
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
							className={chip(on)}
						>
							{titleCase(c.category)}{" "}
							<span className="num opacity-70">{c.count}</span>
						</button>
					);
				})}
			</fieldset>
			<fieldset
				className="m-0 mt-2 flex min-w-0 flex-wrap gap-2 border-0 p-0"
				aria-label="Filter by horizon"
			>
				{HORIZONS.map((h) => {
					const on = horizon === h;
					return (
						<button
							key={h}
							type="button"
							aria-pressed={on}
							onClick={() => setHorizon(on ? null : h)}
							className={chip(on)}
						>
							{titleCase(h)}
						</button>
					);
				})}
			</fieldset>
			<div className="mt-4" data-testid="risk-actions">
				<ActionTable actions={risks} />
			</div>
			<section
				className="mt-10 border-t border-rule pt-4"
				data-testid="dq-lane"
				aria-labelledby="dq-h"
			>
				<h2 id="dq-h" className="text-[22px]">
					Data quality and coverage{" "}
					<span className="num text-base font-normal text-ink-muted">
						({dataQuality.length})
					</span>
				</h2>
				<p className="mt-2 max-w-[760px] text-xs text-ink-muted">
					Gaps in the analysis, such as clients whose report produced no
					actions. Kept apart so they do not crowd out client risks.
				</p>
				<div className="mt-3">
					<ActionTable actions={dataQuality} empty="No data-quality items." />
				</div>
			</section>
		</>
	);
}

const route = getRouteApi("/actions");

export function ActionsPage() {
	const query = useData<Overview>("/overview");
	const { tier } = route.useSearch();
	const navigate = route.useNavigate();
	return (
		<>
			<PageHeader
				eyebrow="Actions"
				title="Every next action, and the gaps behind them"
			/>
			<StateBoundary query={query} label="Loading the actions">
				{(ov) => (
					<ActionsView
						overview={ov}
						tier={tier ?? null}
						onTier={(t) =>
							navigate({
								search: (prev) => ({ ...prev, tier: t ?? undefined }),
								replace: true,
							})
						}
					/>
				)}
			</StateBoundary>
		</>
	);
}
