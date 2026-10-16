import { describe, expect, it } from "vitest";
import { breachLabel, worstBreachLabel } from "./status";

describe("breach reconciliation labels", () => {
	it("says waiver claimed with the note id", () => {
		expect(
			breachLabel({
				status: "client_directed",
				note_ids: ["N-010"],
				waiver_claimed: true,
			}),
		).toBe("waiver claimed (N-010)");
	});
	it("names a client instruction without a waiver", () => {
		expect(
			breachLabel({ status: "client_directed", note_ids: ["N-013"] }),
		).toBe("client instruction (N-013)");
	});
	it("labels acknowledged and contradicted", () => {
		expect(breachLabel({ status: "acknowledged", note_ids: ["N-024"] })).toBe(
			"acknowledged (N-024)",
		);
		expect(breachLabel({ status: "contradicted", note_ids: ["N-008"] })).toBe(
			"contradicted (N-008)",
		);
	});
	it("adds no label for no_note", () => {
		expect(breachLabel({ status: "no_note", note_ids: [] })).toBeNull();
		expect(worstBreachLabel([{ status: "no_note", note_ids: [] }])).toBeNull();
		expect(worstBreachLabel(undefined)).toBeNull();
		expect(worstBreachLabel([])).toBeNull();
	});
	it("picks the most consequential status and joins its notes", () => {
		expect(
			worstBreachLabel([
				{ status: "acknowledged", note_ids: ["N-001"] },
				{ status: "contradicted", note_ids: ["N-008"] },
				{ status: "contradicted", note_ids: ["N-009", "N-008"] },
			]),
		).toBe("contradicted (N-008, N-009)");
	});
});
