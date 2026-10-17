import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { computedResult } from "./fixtures";
import {
	breachTone,
	ScenarioComparison,
	ScenarioResultView,
} from "./ScenarioTab";

const placeholder = computedResult({
	status: "placeholder",
	note: "Illustrative, not computed: fixed data.",
	summary: "",
});
const notRun = computedResult({
	status: "placeholder",
	note: "Not computed: scenarios have not been run for this date. No figures are shown.",
	cases: {},
	positions: [],
	summary: "",
	market: null,
});

describe("ScenarioResultView, computed", () => {
	it("shows the three cases together as a range", () => {
		render(<ScenarioResultView result={computedResult()} />);
		const range = screen.getByTestId("case-range");
		for (const c of ["worst", "likely", "best"])
			expect(within(range).getByTestId(`case-${c}`)).toBeInTheDocument();
		expect(screen.getByTestId("case-worst")).toHaveTextContent("-8.0%");
		expect(screen.getByTestId("case-likely")).toHaveTextContent("-3.0%");
		expect(screen.getByTestId("case-best")).toHaveTextContent("+2.0%");
		expect(screen.getByTestId("case-likely")).toHaveTextContent("USD -30,000");
	});

	it("carries the conditional, not-a-probability banner with the horizon", () => {
		render(<ScenarioResultView result={computedResult()} />);
		const banner = screen.getByTestId("conditional-banner");
		expect(banner).toHaveTextContent(
			"Conditional on this scenario, over 3 months",
		);
		expect(banner).toHaveTextContent("not a probability");
		expect(screen.queryByTestId("placeholder-banner")).toBeNull();
		expect(banner).not.toHaveClass(
			"text-alert",
			"border-alert",
			"bg-alert-sunk",
		);
	});

	it("opens the explainer of the likely change", () => {
		render(<ScenarioResultView result={computedResult()} />);
		expect(
			screen.queryByText(/applies every channel's likely move/),
		).toBeNull();
		fireEvent.click(
			screen.getByRole("button", { name: "Explain the likely change" }),
		);
		expect(
			screen.getByText(/applies every channel's likely move together/),
		).toBeInTheDocument();
	});

	it("renders every part: summaries, premise, event, horizon, collateral and bands per case, positions", () => {
		render(<ScenarioResultView result={computedResult()} />);
		expect(screen.getByTestId("scenario-summary")).toHaveTextContent(
			"loss of 3.0%",
		);
		expect(screen.getByTestId("market-summary")).toHaveTextContent("Energy up");
		for (const t of [
			"Premise",
			"Mirrors the event",
			"Horizon",
			"Caveat",
			"Collateral effects",
			"Mandate bands crossed",
			"Per position",
		])
			expect(screen.getByText(t)).toBeInTheDocument();
		expect(screen.getByText("3 months")).toBeInTheDocument();
		expect(screen.getAllByText(/Worst case ·/)).toHaveLength(2);
		expect(screen.getByText(/CF-1: LTV 58.0% to 80.0%/)).toBeInTheDocument();
		expect(screen.getByText(/shortfall USD 1,200/)).toBeInTheDocument();
		expect(screen.getByText(/crosses out of the band/)).toBeInTheDocument();
		expect(screen.getByText("US Core Fund")).toBeInTheDocument();
		expect(screen.getByText("Untouched")).toBeInTheDocument();
		expect(screen.getByText(/equity_us -3.0%/)).toBeInTheDocument();
	});

	it("marks a computed breach with caution, never the alarm colour", () => {
		render(<ScenarioResultView result={computedResult()} />);
		const b = screen.getByText(/crosses the trigger/);
		expect(b).toHaveClass("text-caution");
		expect(b).not.toHaveClass("text-alert");
		expect(breachTone(false)).toBe("text-caution");
	});

	it("shows partial status and the gaps", () => {
		render(
			<ScenarioResultView
				result={computedResult({
					status: "partial",
					gaps: [
						{ kind: "no_data", description: "no move for channel(s) gold" },
					],
				})}
			/>,
		);
		expect(screen.getByTestId("partial-notice")).toBeInTheDocument();
		expect(screen.getByTestId("gaps")).toHaveTextContent(
			"no move for channel(s) gold",
		);
	});

	it("lists the market moves with their anchor", () => {
		render(<ScenarioResultView result={computedResult()} />);
		expect(
			screen.getByText("Market moves behind this scenario"),
		).toBeInTheDocument();
		expect(screen.getByText(/Not anchored to history/)).toBeInTheDocument();
	});
});

describe("ScenarioResultView, not computed", () => {
	it("marks illustrative results and keeps breach colours neutral", () => {
		render(<ScenarioResultView result={placeholder} />);
		expect(screen.getByTestId("placeholder-banner")).toHaveTextContent(
			"Illustrative, not computed",
		);
		expect(screen.queryByTestId("conditional-banner")).toBeNull();
		expect(screen.getByText(/crosses the trigger/)).not.toHaveClass(
			"text-alert",
			"text-caution",
		);
		expect(breachTone(true)).toBe("text-ink-2");
	});

	it("shows the note and no figures when the scenario was not run", () => {
		render(<ScenarioResultView result={notRun} />);
		expect(screen.getByText(/scenarios have not been run/)).toBeInTheDocument();
		expect(screen.queryByTestId("case-range")).toBeNull();
		expect(screen.queryByText("Per position")).toBeNull();
		expect(screen.getByText("The blockade widens.")).toBeInTheDocument();
	});
});

describe("ScenarioComparison", () => {
	it("shows likely and worst, percent and USD, for every scenario", () => {
		render(
			<ScenarioComparison
				results={[
					computedResult(),
					computedResult({
						scenario_id: "s2",
						name: "Rates higher",
						cases: {
							...computedResult().cases,
							likely: {
								...computedResult().cases.likely,
								delta_pct: -1.5,
								delta_usd: -15000,
							},
						},
					}),
					computedResult({ ...notRun, scenario_id: "s3", name: "Not run" }),
				]}
			/>,
		);
		const rows = screen.getAllByRole("row");
		expect(rows).toHaveLength(4);
		expect(within(rows[1]).getByText("-3.0%")).toBeInTheDocument();
		expect(within(rows[1]).getByText("-8.0%")).toBeInTheDocument();
		expect(within(rows[1]).getByText("USD -30,000")).toBeInTheDocument();
		expect(within(rows[2]).getByText("-1.5%")).toBeInTheDocument();
		expect(within(rows[3]).getByText("Not computed")).toBeInTheDocument();
	});
});
