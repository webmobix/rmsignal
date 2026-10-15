import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { breachTone, ScenarioResultView } from "./ScenarioTab";

const result = {
	scenario_id: "s1",
	name: "Anything",
	premise: "P",
	mirrors: "M",
	caveat: "C",
	status: "placeholder",
	note: "Illustrative, not computed: fixed data.",
	before_usd: 100,
	after_usd: 103,
	delta_usd: 3,
	delta_pct: 3,
	reached_pct: 60,
	untouched_count: 2,
	collateral: [
		{
			facility: "F",
			ltv_before_pct: 58,
			ltv_after_pct: 80,
			trigger_pct: 75,
			breaches: true,
			shortfall_usd: null,
		},
	],
	bands: [
		{
			asset_class: "Equity",
			portfolio: "PF",
			before_pct: 34,
			after_pct: 36,
			band_min_pct: 20,
			band_max_pct: 35,
			crosses: "out",
		},
	],
	positions: [
		{
			instrument: "Pos",
			asset_class: "Equity",
			weight_pct: 18,
			move_pct: 6,
			delta_usd: 1,
			channels: [{ channel: "Ch", pct: 6, why: "W" }],
		},
	],
} as never;

describe("ScenarioResultView", () => {
	it("shows the placeholder banner and renders every part", () => {
		render(<ScenarioResultView result={result} />);
		expect(screen.getByTestId("placeholder-banner")).toHaveTextContent(
			"Illustrative, not computed",
		);
		for (const t of [
			"Premise",
			"Mirrors the event",
			"Caveat",
			"Collateral effects",
			"Mandate bands crossed",
			"Per position",
		])
			expect(screen.getByText(t)).toBeInTheDocument();
		expect(screen.getByText("Pos")).toBeInTheDocument();
	});
	it("uses neutral breach colours for placeholders, alert for computed", () => {
		render(<ScenarioResultView result={result} />);
		expect(screen.getByText(/crosses the trigger/)).not.toHaveClass(
			"text-alert",
		);
		expect(breachTone(false)).toBe("text-alert");
	});
});
