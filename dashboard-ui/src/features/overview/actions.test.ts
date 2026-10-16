import { describe, expect, it } from "vitest";
import type { ApiAction } from "#/api/queries";
import { splitActions, tierCounts, urgentActions } from "./actions";

const mk = (
	id: string,
	importance: string,
	category: string,
	horizon = "later",
) => ({ action_id: id, importance, category, horizon }) as unknown as ApiAction;
const actions = [
	mk("a", "high", "concentration_risk"),
	mk("b", "medium", "mandate_drift"),
	mk("c", "high", "data_quality"),
	mk("d", "medium", "data_quality"),
];

describe("splitActions", () => {
	it("keeps data quality in its own lane", () => {
		const { risks, dataQuality } = splitActions(actions, {
			tier: null,
			category: null,
		});
		expect(risks.map((a) => a.action_id)).toEqual(["a", "b"]);
		expect(dataQuality.map((a) => a.action_id)).toEqual(["c", "d"]);
	});
	it("filters both lanes by tier", () => {
		const { risks, dataQuality } = splitActions(actions, {
			tier: "high",
			category: null,
		});
		expect(risks.map((a) => a.action_id)).toEqual(["a"]);
		expect(dataQuality.map((a) => a.action_id)).toEqual(["c"]);
	});
	it("category only narrows risks", () => {
		const { risks, dataQuality } = splitActions(actions, {
			tier: null,
			category: "mandate_drift",
		});
		expect(risks.map((a) => a.action_id)).toEqual(["b"]);
		expect(dataQuality).toHaveLength(2);
	});
});
describe("horizon filter", () => {
	const hs = [
		mk("a", "high", "mandate_drift", "immediate"),
		mk("b", "high", "mandate_drift", "later"),
		mk("c", "high", "data_quality", "later"),
	];
	it("narrows risks only", () => {
		const { risks, dataQuality } = splitActions(hs, {
			tier: null,
			category: null,
			horizon: "immediate",
		});
		expect(risks.map((a) => a.action_id)).toEqual(["a"]);
		expect(dataQuality.map((a) => a.action_id)).toEqual(["c"]);
	});
});
describe("urgentActions", () => {
	it("keeps only critical/high immediate non-data-quality actions", () => {
		const list = [
			mk("a", "critical", "mandate_drift", "immediate"),
			mk("b", "high", "mandate_drift", "within_30_days"),
			mk("c", "medium", "mandate_drift", "immediate"),
			mk("d", "critical", "data_quality", "immediate"),
			mk("e", "high", "concentration_risk", "immediate"),
		];
		expect(urgentActions(list).map((a) => a.action_id)).toEqual(["a", "e"]);
	});
});
describe("tierCounts", () => {
	it("counts per tier", () =>
		expect(tierCounts(actions)).toEqual({ high: 2, medium: 2 }));
});
