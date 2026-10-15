import {
	areaY,
	colorLegend,
	defineChart,
	ruleX,
	stack,
} from "@tanstack/charts";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { tooltip } from "@tanstack/charts/tooltip";
import { scaleUtc } from "d3-scale";
import { useMemo } from "react";
import { CHART_COLORS } from "#/lib/chart";
import { fmtCompact } from "#/lib/format";
import { ChartFrame } from "../ChartFrame";

export interface HistorySeries {
	id: string;
	label: string;
	points: { date: string; value: number }[];
}

interface Row {
	date: Date;
	value: number;
	series: string;
}

/** Stacked AuM by series over the snapshots, with vertical markers at event dates. */
export function StackedHistory({
	series,
	eventDates = [],
	ariaLabel,
	height = 320,
}: {
	series: HistorySeries[];
	eventDates?: string[];
	ariaLabel: string;
	height?: number;
}) {
	const definition = useMemo(() => {
		const rows: Row[] = series.flatMap((s) =>
			s.points.map((p) => ({
				date: new Date(p.date),
				value: p.value,
				series: s.label,
			})),
		);
		const events = eventDates.map((d) => ({ date: new Date(d) }));
		const labels = series.map((s) => s.label);
		return defineChart({
			marks: [
				areaY(rows, {
					x: "date",
					y: "value",
					color: "series",
					layout: stack({ order: labels }),
					fillOpacity: 0.85,
				}),
				ruleX(events, {
					x: "date",
					strokeDasharray: "2 3",
					strokeOpacity: 0.55,
				}),
			],
			scales: {
				x: { scale: scaleUtc },
				y: {
					scale: scaleLinear,
					nice: true,
					grid: true,
					axis: {
						label: "AuM (USD)",
						ticks: { format: (v: number) => fmtCompact(v) },
					},
				},
			},
			color: {
				legend: colorLegend({ label: "Portfolio" }),
				domain: labels,
				range: labels.map(
					(_, i) => CHART_COLORS[i % CHART_COLORS.length] ?? "",
				),
			},
			tooltip,
		});
	}, [series, eventDates]);
	return (
		<ChartFrame definition={definition} ariaLabel={ariaLabel} height={height} />
	);
}
