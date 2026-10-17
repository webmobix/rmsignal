import { defineChart, dot, text } from "@tanstack/charts";
import { decorative } from "@tanstack/charts/mark/decorative";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { tooltip } from "@tanstack/charts/tooltip";
import { useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import type { Overview } from "#/api/queries";
import { ChartFrame } from "#/components/ChartFrame";
import { aumScale } from "#/lib/chart";
import { fmtUsd } from "#/lib/format";
import { TIER_COLOR, TIER_LABEL } from "#/lib/tiers";

type Row = Overview["client_rows"][number];
type Point = Row & {
	urgency: number;
	tier: string;
	label: string | null;
	labelDy: number;
};

const TOP_N = 10;

/** The clients with the most urgent action; the rest stay reachable from the client list. */
export function toPoints(all: Row[], limit = TOP_N): Point[] {
	const rows = [...all]
		.sort((a, b) => (b.max_urgency ?? 0) - (a.max_urgency ?? 0))
		.slice(0, limit);
	// neighbours in AuM order alternate above and below their dot so labels do not collide
	const order = new Map(
		[...rows]
			.sort((a, b) => a.aum_usd - b.aum_usd)
			.map((r, i) => [r.client_id, i]),
	);
	return rows.map((r) => ({
		...r,
		urgency: r.max_urgency ?? 0,
		tier: r.top_importance ?? "none",
		label: r.action_count > 0 ? r.client_id.replace(/^CL-0*/, "") : null,
		labelDy: (order.get(r.client_id) ?? 0) % 2 === 0 ? -13 : 20,
	}));
}

export function ClientMatrix({ rows }: { rows: Row[] }) {
	const navigate = useNavigate();
	const [topOnly, setTopOnly] = useState(true);
	const points = useMemo(
		() => toPoints(rows, topOnly ? TOP_N : rows.length),
		[rows, topOnly],
	);
	const lo = Math.min(...points.map((p) => p.aum_usd));
	const hi = Math.max(...points.map((p) => p.aum_usd));
	const definition = useMemo(
		() =>
			defineChart({
				marks: [
					dot(points, {
						x: "aum_usd",
						y: "urgency",
						key: "client_id",
						r: 7,
						color: "tier",
					}),
					decorative(
						text(
							points.filter((p) => p.label),
							{
								x: "aum_usd",
								y: "urgency",
								text: "label",
								dy: (p: Point) => p.labelDy,
								fontSize: 12,
							},
						),
					),
				],
				scales: {
					x: {
						scale: aumScale(lo * 0.85, hi * 1.15),
						axis: { label: "Assets under management (USD, log scale)" },
					},
					y: {
						scale: scaleLinear,
						nice: true,
						grid: true,
						axis: { label: "Urgency of the most pressing action" },
					},
				},
				color: {
					domain: ["critical", "high", "medium", "low", "none"],
					range: ["critical", "high", "medium", "low", "none"].map(
						(t) => TIER_COLOR[t] ?? "",
					),
				},
				focus: "nearest",
				maxFocusDistance: 16,
				tooltip: { use: tooltip, className: "matrix-tooltip", offset: 12 },
			}),
		[points, lo, hi],
	);
	return (
		<div>
			<label className="mb-2 flex w-fit cursor-pointer items-center gap-2 text-sm text-ink-2">
				<button
					type="button"
					role="switch"
					aria-checked={topOnly}
					onClick={() => setTopOnly((v) => !v)}
					className={`relative h-5 w-9 rounded-full border border-navy-700 transition-colors ${topOnly ? "bg-navy-700" : "bg-surface"}`}
				>
					<span
						className={`absolute top-0.5 h-3.5 w-3.5 rounded-full transition-all ${topOnly ? "left-[18px] bg-surface" : "left-0.5 bg-navy-700"}`}
					/>
				</button>
				Top {TOP_N} by urgency
			</label>
			<ChartFrame<Point>
				definition={definition}
				ariaLabel="Clients by assets under management and urgency"
				height={400}
				onSelect={(p) =>
					p &&
					navigate({
						to: "/clients/$clientId",
						params: { clientId: p.client_id },
					})
				}
				tooltipBody={(p) => (
					<div className="text-xs">
						<div className="font-semibold">{p.client_name}</div>
						<div>{fmtUsd(p.aum_usd)}</div>
						<div>
							{p.action_count} action{p.action_count === 1 ? "" : "s"} ·{" "}
							{TIER_LABEL[p.tier]}
						</div>
					</div>
				)}
				caption="Each point is a client; the switch limits it to the ten with the most urgent action. Colour shows the top importance and the number is the client ID; clients without actions sit on the baseline. Select a point to open the client."
			/>
		</div>
	);
}
