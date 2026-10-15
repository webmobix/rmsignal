import { defineChart, dot, ruleY, text } from "@tanstack/charts";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { tooltip } from "@tanstack/charts/tooltip";
import { useNavigate } from "@tanstack/react-router";
import { useMemo } from "react";
import type { Overview } from "#/api/queries";
import { ChartFrame } from "#/components/ChartFrame";
import { aumScale } from "#/lib/chart";
import { fmtUsd } from "#/lib/format";
import { TIER_COLOR, TIER_LABEL } from "#/lib/tiers";

type Row = Overview["client_rows"][number];
type Point = Row & { urgency: number; tier: string; label: string | null };

const BANDS = [
	{ y: 28, text: "Medium ≥ 28" },
	{ y: 52, text: "High ≥ 52" },
	{ y: 76, text: "Critical ≥ 76" },
];

export function toPoints(rows: Row[]): Point[] {
	return rows.map((r) => ({
		...r,
		urgency: r.max_urgency ?? 0,
		tier: r.top_importance ?? "none",
		label: r.action_count > 0 ? r.client_id : null,
	}));
}

export function ClientMatrix({ rows }: { rows: Row[] }) {
	const navigate = useNavigate();
	const points = useMemo(() => toPoints(rows), [rows]);
	const definition = useMemo(
		() =>
			defineChart({
				marks: [
					ruleY(
						BANDS.map((b) => b.y),
						{ strokeDasharray: "3 3", strokeOpacity: 0.6 },
					),
					text(BANDS, {
						x: () => 1.2e8,
						y: "y",
						text: "text",
						anchor: "end",
						dy: -7,
						fontSize: 10,
						fill: "var(--color-ink-muted)",
					}),
					dot(points, {
						x: "aum_usd",
						y: "urgency",
						key: "client_id",
						r: 7,
						color: "tier",
					}),
					text(
						points.filter((p) => p.label),
						{
							x: "aum_usd",
							y: "urgency",
							text: "label",
							dy: -13,
							fontSize: 10,
						},
					),
				],
				scales: {
					x: {
						scale: aumScale(),
						grid: true,
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
				tooltip,
			}),
		[points],
	);
	return (
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
			caption="Each point is a client. Colour and the tier label show the top importance; clients without actions sit on the baseline. Select a point to open the client."
		/>
	);
}
