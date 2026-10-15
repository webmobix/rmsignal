import { describe, expect, it } from "vitest";
import { healthItems } from "./Health";

const detail = {
	profile: { kyc_overdue: true, kyc_review_due: "2026-08-01" },
	portfolios: [
		{ mandate_status: "out_of_band" },
		{ mandate_status: "no_mandate" },
	],
	actions: [],
	consolidated: {
		look_through: [{ name: "Aranya", share_pct: 68.4 }],
		liquidity: { shortfall_usd: 0, coverage_ratio: 2.1 },
		facilities: [{ ltv_gap_pp: 1.3, current: { ltv_pct: 73.7 } }],
	},
} as never;

describe("healthItems", () => {
	it("derives five statuses with figures", () => {
		const items = Object.fromEntries(
			healthItems(detail).map((i) => [i.key, i]),
		);
		expect(items.concentration?.status).toBe("alert");
		expect(items.mandate?.figure).toBe("1 portfolio out of band");
		expect(items.liquidity?.status).toBe("ok");
		expect(items.credit?.status).toBe("alert");
		expect(items.kyc?.status).toBe("alert");
	});
	it("copes with no facility and no liquidity data", () => {
		const d = {
			...(detail as object),
			consolidated: { look_through: [], liquidity: null, facilities: [] },
		} as never;
		const items = Object.fromEntries(healthItems(d).map((i) => [i.key, i]));
		expect(items.credit?.figure).toBe("No credit facility");
		expect(items.liquidity?.figure).toBe("No liquidity data");
	});
});
