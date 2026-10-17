import { defineChart, dot, lineY, ruleY, text } from "@tanstack/charts";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { tooltip } from "@tanstack/charts/tooltip";
import { scaleUtc } from "d3-scale";
import { useMemo } from "react";
import { ChartFrame } from "../ChartFrame";

export interface TrendPoint {
	date: string;
	value: number;
}

/** A single line over the snapshots, with an optional reference rule (e.g. a margin-call trigger). */
export function LineTrend({
	points,
	ariaLabel,
	yLabel,
	rule,
	height = 260,
	format,
}: {
	points: TrendPoint[];
	ariaLabel: string;
	yLabel: string;
	rule?: { value: number; label: string };
	height?: number;
	format?: (v: number) => string;
}) {
	const definition = useMemo(() => {
		const rows = points.map((p) => ({
			date: new Date(p.date),
			value: p.value,
		}));
		const ruleRows = rule
			? [{ y: rule.value, text: rule.label, x: rows[rows.length - 1]?.date }]
			: [];
		return defineChart({
			marks: [
				lineY(rows, {
					x: "date",
					y: "value",
					stroke: "var(--color-navy-700)",
					strokeWidth: 2,
				}),
				dot(rows, {
					x: "date",
					y: "value",
					r: 4,
					fill: "var(--color-navy-700)",
				}),
				ruleY(
					ruleRows.map((r) => r.y),
					{
						stroke: "var(--color-alert)",
						strokeDasharray: "5 3",
						strokeOpacity: 0.9,
					},
				),
				text(ruleRows, {
					x: "x",
					y: "y",
					text: "text",
					dy: -8,
					anchor: "end",
					fontSize: 12,
					fill: "var(--color-alert)",
				}),
			],
			scales: {
				x: { scale: scaleUtc },
				y: {
					scale: scaleLinear,
					nice: true,
					grid: true,
					axis: { label: yLabel, ticks: format ? { format } : undefined },
				},
			},
			tooltip,
		});
	}, [points, rule, yLabel, format]);
	return (
		<ChartFrame definition={definition} ariaLabel={ariaLabel} height={height} />
	);
}
