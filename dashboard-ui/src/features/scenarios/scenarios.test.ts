import { describe, expect, it } from "vitest";
import {
	barPosition,
	conditionalBanner,
	hasFigures,
	isComputed,
} from "./scenarios";

describe("scenarios helpers", () => {
	it("places values on a bar that always includes zero", () => {
		const v = [-10, -4, 6];
		expect(barPosition(-10, v)).toBe(0);
		expect(barPosition(6, v)).toBe(100);
		expect(barPosition(0, v)).toBeCloseTo(62.5);
		expect(barPosition(3, [3, 3, 3])).toBe(100);
		expect(barPosition(0, [0, 0, 0])).toBe(50);
	});
	it("needs all three cases to have figures", () => {
		expect(hasFigures({ cases: {} })).toBe(false);
		expect(hasFigures({ cases: { worst: 1, likely: 1 } })).toBe(false);
		expect(hasFigures({ cases: { worst: 1, likely: 1, best: 1 } })).toBe(true);
	});
	it("treats partial results as computed and placeholders as not", () => {
		expect(isComputed("computed")).toBe(true);
		expect(isComputed("partial")).toBe(true);
		expect(isComputed("placeholder")).toBe(false);
		expect(isComputed("insufficient_data")).toBe(false);
	});
	it("states the horizon and that the likely case is not a probability", () => {
		expect(conditionalBanner(6)).toMatch(/over 6 months/);
		expect(conditionalBanner(3)).toMatch(/not a probability/);
	});
});
