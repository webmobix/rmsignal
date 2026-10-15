import { describe, expect, it } from "vitest";
import type { ApiAction } from "#/api/queries";
import { splitActions, tierCounts } from "./actions";

const mk = (id: string, importance: string, category: string) =>
	({ action_id: id, importance, category }) as unknown as ApiAction;
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
describe("tierCounts", () => {
	it("counts per tier", () =>
		expect(tierCounts(actions)).toEqual({ high: 2, medium: 2 }));
});
