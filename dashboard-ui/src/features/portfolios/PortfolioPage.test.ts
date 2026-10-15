import { describe, expect, it } from "vitest";
import { bandStatement } from "./PortfolioPage";

const band = {
	asset_class: "Equity",
	weight_pct: 71.5,
	min_pct: 10,
	target_pct: 20,
	max_pct: 30,
	out_of_band: true,
} as never;

describe("bandStatement", () => {
	it("states weight and the maximum when above", () => {
		expect(bandStatement(band)).toBe(
			"Equity: weight 71.5% is 41.5pp above the maximum of 30.0%.",
		);
	});
	it("states the minimum when below", () => {
		expect(bandStatement({ ...(band as object), weight_pct: 5 } as never)).toBe(
			"Equity: weight 5.0% is 5.0pp below the minimum of 10.0%.",
		);
	});
	it("is null when within band", () => {
		expect(
			bandStatement({ ...(band as object), out_of_band: false } as never),
		).toBeNull();
	});
});
