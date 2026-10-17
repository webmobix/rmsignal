import { useState } from "react";
import type { Schemas } from "#/api/client";
import { SectorChart } from "#/components/charts/SectorChart";
import { EmptyNotice } from "#/components/StateBoundary";
import { Tabs } from "#/components/Tabs";
import { fmtPct } from "#/lib/format";

type Exposure = Schemas["PortfolioDetail"]["sector_exposure"];
type View = "direct" | "look_through";

const ASSET_TYPE_LABELS = [
	"Diversified",
	"Corporate",
	"Sovereign",
	"Cash",
	"Gold",
	"Multi",
	"Macro",
];

/** Percentage of the portfolio that sits in an unclassified group, for the note under the chart. */
export function unclassifiedPct(groups: Exposure["direct"]): number {
	return groups
		.filter(
			(g) =>
				g.name === "unclassified" || g.name === "Unclassified (look-through)",
		)
		.reduce((sum, g) => sum + g.exposure_pct, 0);
}

export function SectorSection({ exposure }: { exposure: Exposure }) {
	const [view, setView] = useState<View>("direct");
	const groups = exposure[view];
	if (!groups.length) {
		return (
			<EmptyNotice>No positions to show a sector exposure for.</EmptyNotice>
		);
	}
	const unclassified = unclassifiedPct(groups);
	const present = ASSET_TYPE_LABELS.filter((l) =>
		groups.some((g) => g.name === l),
	);
	return (
		<div data-testid="sector-section">
			<Tabs
				tabs={[
					{ id: "direct", label: "Direct" },
					{ id: "look_through", label: "Look-through" },
				]}
				value={view}
				onChange={(id) => setView(id as View)}
			/>
			<div className="mt-4">
				<SectorChart
					groups={groups}
					ariaLabel={`Portfolio exposure by sector, ${view === "direct" ? "direct" : "looked through structured products"}`}
				/>
			</div>
			<ul className="mt-3 space-y-1 text-ink-2" data-testid="sector-notes">
				<li>
					{view === "direct"
						? "Each position counts under its instrument's sector."
						: "Structured products are replaced by their underlyings, each under the sector of the instrument it matches by name."}{" "}
					Percentages are of {exposure.denominator_label}. The mandates define
					no sector limits, so nothing here is checked against them.
				</li>
				{unclassified > 0 ? (
					<li data-testid="sector-unclassified">
						<b>{fmtPct(unclassified)}</b> of the portfolio is unclassified
						{view === "look_through"
							? ": an underlying matches no instrument, or a product's underlying cannot be identified."
							: ": the instrument has no sector."}
					</li>
				) : null}
				{view === "look_through" && exposure.basket_attribution_assumption ? (
					<li>
						Basket products are split equally across their underlyings; this is
						an assumption, not a sensitivity.
					</li>
				) : null}
				{present.length ? (
					<li>
						{present.join(", ")} {present.length > 1 ? "are" : "is an"}{" "}
						asset-type label{present.length > 1 ? "s" : ""} in the source data,
						not {present.length > 1 ? "sectors" : "a sector"}.
					</li>
				) : null}
			</ul>
		</div>
	);
}
