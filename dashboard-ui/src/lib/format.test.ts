import { describe, expect, it } from "vitest";
import { fmtDate, fmtPct, fmtUsd, initials } from "./format";

describe("format", () => {
	it("formats dates in UTC", () =>
		expect(fmtDate("2026-08-26")).toBe("26 Aug 2026"));
	it("builds initials", () => expect(initials("Priscilla Ong")).toBe("PO"));
	it("compacts USD", () => {
		expect(fmtUsd(46_699_200)).toBe("USD 46.7m");
		expect(fmtUsd(46_699_200, false)).toBe("USD 46,699,200");
	});
	it("signs percentages", () => expect(fmtPct(1.234, 1, true)).toBe("+1.2%"));
});
