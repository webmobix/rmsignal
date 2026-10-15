import { barX, defineChart, dot, tickX } from "@tanstack/charts";
import { scaleBand } from "@tanstack/charts/scales/band";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { tooltip } from "@tanstack/charts/tooltip";
import { useMemo } from "react";
import { ChartFrame } from "../ChartFrame";

export interface Band {
	asset_class: string;
	weight_pct: number;
	min_pct: number;
	target_pct: number;
	max_pct: number;
	out_of_band: boolean;
}

/** Mandate bands: min-to-max range per asset class, target tick, actual weight as a dot. */
export function BandsChart({ bands }: { bands: Band[] }) {
	const definition = useMemo(() => {
		const classes = bands.map((b) => b.asset_class);
		const rows = bands.map((b) => ({
			...b,
			state: b.out_of_band ? "Out of band" : "Within band",
		}));
		return defineChart({
			marks: [
				barX(rows, {
					x1: "min_pct",
					x2: "max_pct",
					y: "asset_class",
					key: "asset_class",
					fill: "var(--color-muted-blue)",
					fillOpacity: 0.6,
					inset: 5,
				}),
				tickX(rows, {
					x: "target_pct",
					y: "asset_class",
					stroke: "var(--color-navy-950)",
					strokeWidth: 2,
				}),
				dot(rows, {
					x: "weight_pct",
					y: "asset_class",
					key: "asset_class",
					r: 6,
					color: "state",
				}),
			],
			scales: {
				x: {
					scale: scaleLinear,
					nice: true,
					grid: true,
					axis: { label: "Weight (% of portfolio)" },
				},
				y: { scale: () => scaleBand<string>().domain(classes).padding(0.2) },
			},
			color: {
				domain: ["Within band", "Out of band"],
				range: ["var(--color-navy-700)", "var(--color-alert)"],
			},
			tooltip,
		});
	}, [bands]);
	return (
		<ChartFrame
			definition={definition}
			ariaLabel="Actual weight against mandate bands by asset class"
			height={Math.max(180, bands.length * 34 + 60)}
			caption="Shaded range is the mandate minimum to maximum; the dark tick is the target; the dot is the actual weight, red when outside the band."
		/>
	);
}
