import { barX, defineChart } from "@tanstack/charts";
import { scaleBand } from "@tanstack/charts/scales/band";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { tooltip } from "@tanstack/charts/tooltip";
import { useMemo } from "react";
import { fmtCompact } from "#/lib/format";
import { ChartFrame } from "../ChartFrame";

export interface BarRow {
	key: string;
	label: string;
	value: number;
}

/** Horizontal ranked bars. The order of `rows` is the order shown top to bottom. */
export function BarList({
	rows,
	ariaLabel,
	valueLabel,
	onSelect,
	rowHeight = 22,
	format,
}: {
	rows: BarRow[];
	ariaLabel: string;
	valueLabel: string;
	onSelect?: (row: BarRow) => void;
	rowHeight?: number;
	format?: (value: number) => string;
}) {
	const definition = useMemo(
		() =>
			defineChart({
				marks: [
					barX(rows, {
						x: "value",
						y: "label",
						key: "key",
						inset: 2,
						fill: "var(--color-navy-700)",
					}),
				],
				scales: {
					x: {
						scale: scaleLinear,
						nice: true,
						grid: true,
						axis: {
							label: valueLabel,
							ticks: {
								format: (v: number) => (format ? format(v) : fmtCompact(v)),
							},
						},
					},
					y: {
						scale: () =>
							scaleBand<string>()
								.domain(rows.map((r) => r.label))
								.padding(0.2),
					},
				},
				tooltip,
			}),
		[rows, valueLabel, format],
	);
	return (
		<ChartFrame<BarRow>
			definition={definition}
			ariaLabel={ariaLabel}
			height={Math.max(140, rows.length * rowHeight + 56)}
			onSelect={onSelect ? (row) => row && onSelect(row) : undefined}
		/>
	);
}
