import { describe, expect, it } from "vitest";
import { perClient } from "./InstrumentPage";
import { byAssetClass, filterHeld } from "./InstrumentsPage";

describe("byAssetClass", () => {
	it("sums held USD per class, drops zero-held and sorts descending", () => {
		const rows = [
			{ asset_class: "Equity", held_usd: 5 },
			{ asset_class: "Equity", held_usd: 7 },
			{ asset_class: "Bonds", held_usd: 20 },
			{ asset_class: "Cash", held_usd: 0 },
		] as never[];
		expect(byAssetClass(rows)).toEqual([
			{ key: "Bonds", label: "Bonds", value: 20 },
			{ key: "Equity", label: "Equity", value: 12 },
		]);
	});
});

describe("perClient", () => {
	it("sums across a client's portfolios", () => {
		const holders = [
			{ client_id: "CL-1", client_name: "A", value_usd: 3 },
			{ client_id: "CL-1", client_name: "A", value_usd: 4 },
			{ client_id: "CL-2", client_name: "B", value_usd: 10 },
		] as never[];
		expect(perClient(holders).map((r) => [r.key, r.value])).toEqual([
			["CL-2", 10],
			["CL-1", 7],
		]);
	});
});

describe("filterHeld", () => {
	const rows = [
		{ held_usd: 0 },
		{ held_usd: null },
		{ held_usd: 5 },
	] as never[];
	it("hides instruments with zero held USD when on", () =>
		expect(filterHeld(rows, true)).toHaveLength(1));
	it("keeps all when off", () =>
		expect(filterHeld(rows, false)).toHaveLength(3));
});
