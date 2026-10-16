import { barX, defineChart } from "@tanstack/charts";
import { scaleBand } from "@tanstack/charts/scales/band";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { tooltip } from "@tanstack/charts/tooltip";
import { useMemo } from "react";
import { fmtPct } from "#/lib/format";
import { ChartFrame } from "../ChartFrame";

export interface SectorGroup {
	name: string;
	exposure_pct: number;
}

export interface SectorRow {
	key: string;
	label: string;
	value: number;
	kind: "Sector" | "Unclassified";
}

/** The two unclassified groups the API returns: no sector on the position, or no match for an underlying. */
export function isUnclassified(name: string): boolean {
	return name === "unclassified" || name === "Unclassified (look-through)";
}

/** Largest first; the unclassified group is drawn last so it reads as the remainder. */
export function sectorRows(groups: SectorGroup[]): SectorRow[] {
	const rows = groups.map(
		(g): SectorRow => ({
			key: g.name,
			label: g.name,
			value: g.exposure_pct,
			kind: isUnclassified(g.name) ? "Unclassified" : "Sector",
		}),
	);
	return rows.sort(
		(a, b) =>
			Number(a.kind === "Unclassified") - Number(b.kind === "Unclassified") ||
			b.value - a.value ||
			a.label.localeCompare(b.label),
	);
}

/** Horizontal bars of exposure by sector. No limit marker: the mandates define no sector limits. */
export function SectorChart({
	groups,
	ariaLabel,
}: {
	groups: SectorGroup[];
	ariaLabel: string;
}) {
	const rows = useMemo(() => sectorRows(groups), [groups]);
	const definition = useMemo(
		() =>
			defineChart({
				marks: [
					barX(rows, {
						x: "value",
						y: "label",
						key: "key",
						inset: 2,
						color: "kind",
					}),
				],
				scales: {
					x: {
						scale: scaleLinear,
						nice: true,
						grid: true,
						axis: {
							label: "Exposure (% of portfolio)",
							ticks: { format: (v: number) => fmtPct(v, 0) },
						},
					},
					y: {
						scale: () =>
							scaleBand<string>()
								.domain(rows.map((r) => r.label))
								.padding(0.2),
					},
				},
				color: {
					domain: ["Sector", "Unclassified"],
					range: ["var(--color-navy-700)", "var(--color-slate-blue)"],
				},
				tooltip,
			}),
		[rows],
	);
	return (
		<ChartFrame<SectorRow>
			definition={definition}
			ariaLabel={ariaLabel}
			height={Math.max(140, rows.length * 24 + 56)}
		/>
	);
}
