import type { ScenarioResult } from "./scenarios";

const caseOf = (delta_pct: number, before = 1_000_000) => ({
	before_usd: before,
	after_usd: before * (1 + delta_pct / 100),
	delta_usd: (before * delta_pct) / 100,
	delta_pct,
	bands: [] as unknown[],
	collateral: [] as unknown[],
});

/** A computed client result in the API's shape; pass overrides to change parts of it. */
export function computedResult(
	over: Record<string, unknown> = {},
): ScenarioResult {
	const worst = {
		...caseOf(-8),
		bands: [
			{
				asset_class: "Equity",
				portfolio: "PF-1",
				before_pct: 34,
				after_pct: 36,
				band_min_pct: 20,
				band_max_pct: 35,
				crosses: "out",
			},
		],
		collateral: [
			{
				facility: "CF-1",
				ltv_before_pct: 58,
				ltv_after_pct: 80,
				trigger_pct: 75,
				breaches: true,
				shortfall_usd: 1200,
			},
		],
	};
	return {
		scenario_id: "s1",
		name: "Gulf deterioration",
		premise: "The blockade widens.",
		mirrors: "Event log 2026-08-05: blockade.",
		caveat: "Conditional on this scenario: not a probability.",
		horizon_months: 3,
		market: {
			status: "computed",
			horizon_months: 3,
			summary: "Energy up, equities down.",
			not_a_probability: "n",
			gaps: [],
			channels: [
				{
					channel: "equity_us",
					best: 2,
					likely: -3,
					worst: -9,
					rationale: "Risk off.",
					explainer: "e",
					evidence_ids: ["ev_1"],
					anchored_event: null,
					anchor_note:
						"Not anchored to history: no comparable past event exists in the event log.",
				},
			],
		},
		status: "computed",
		note: "",
		before_usd: 1_000_000,
		cases: { worst, likely: caseOf(-3), best: caseOf(2) },
		reached_pct: 82,
		untouched_count: 3,
		positions: [
			{
				portfolio_id: "PF-1",
				instrument_id: "SYN-EQ-1",
				instrument: "US Core Fund",
				asset_class: "Equity",
				value_usd: 600_000,
				weight_pct: 60,
				mapping: "rule",
				reason: "",
				moves: {
					worst: { move_pct: -9, delta_usd: -54_000 },
					likely: { move_pct: -3, delta_usd: -18_000 },
					best: { move_pct: 2, delta_usd: 12_000 },
				},
				channels: [
					{
						channel: "equity_us",
						best_pct: 2,
						likely_pct: -3,
						worst_pct: -9,
						why: "US equity",
						agent_assigned: false,
					},
				],
			},
			{
				portfolio_id: "PF-1",
				instrument_id: "SYN-CA-1",
				instrument: "USD Deposit",
				asset_class: "Cash",
				value_usd: 100_000,
				weight_pct: 10,
				mapping: "untouched",
				reason: "no channel reaches this holding",
				moves: {
					worst: { move_pct: 0, delta_usd: 0 },
					likely: { move_pct: 0, delta_usd: 0 },
					best: { move_pct: 0, delta_usd: 0 },
				},
				channels: [],
			},
		],
		portfolios: [],
		coverage: { computed: 1, total: 1, missing: [] },
		summary: "The likely change is a loss of 3.0%.",
		explainers: {
			likely: "The likely case applies every channel's likely move together.",
			worst: "The worst case applies every worst move.",
			best: "The best case applies every best move.",
			reached: "82% of value is reached.",
			collateral: "Collateral moves with the pledged positions.",
			bands: "Weights before and after against the band.",
		},
		gaps: [],
		...over,
	} as unknown as ScenarioResult;
}
