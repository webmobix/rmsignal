import { describe, expect, it } from "vitest";
import { isUnclassified, sectorRows } from "./SectorChart";

describe("sectorRows", () => {
	it("orders largest first and puts unclassified last, marked as such", () => {
		const rows = sectorRows([
			{ name: "Unclassified (look-through)", exposure_pct: 40 },
			{ name: "Energy", exposure_pct: 10 },
			{ name: "Information Technology", exposure_pct: 50 },
		]);
		expect(rows.map((r) => r.label)).toEqual([
			"Information Technology",
			"Energy",
			"Unclassified (look-through)",
		]);
		expect(rows.map((r) => r.kind)).toEqual([
			"Sector",
			"Sector",
			"Unclassified",
		]);
		expect(rows[0]).toMatchObject({ key: "Information Technology", value: 50 });
	});
	it("treats both unclassified names as unclassified and asset-type labels as sectors", () => {
		expect(isUnclassified("unclassified")).toBe(true);
		expect(isUnclassified("Unclassified (look-through)")).toBe(true);
		expect(isUnclassified("Diversified")).toBe(false);
	});
});
