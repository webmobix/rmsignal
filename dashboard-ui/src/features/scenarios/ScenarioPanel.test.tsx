import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RollupView, ScenarioPanel } from "./ScenarioPanel";

const state = vi.hoisted(() => ({ data: {} as Record<string, unknown> }));

vi.mock("@tanstack/react-router", () => ({
	Link: ({
		to,
		params,
		search,
		children,
	}: {
		to: string;
		params?: Record<string, string>;
		search?: Record<string, string>;
		children?: React.ReactNode;
	}) => (
		<a
			href={`${to.replace("$clientId", params?.clientId ?? "")}?${new URLSearchParams(search).toString()}`}
		>
			{children}
		</a>
	),
}));
vi.mock("#/api/queries", () => ({
	useData: (path: string) => ({
		data: state.data[path],
		isPending: state.data[path] === undefined,
		isError: false,
		error: null,
		refetch: () => undefined,
	}),
}));
vi.mock("#/components/IdLink", () => ({
	IdLink: ({ id, children }: { id: string; children?: React.ReactNode }) => (
		<a href={`#${id}`}>{children ?? id}</a>
	),
}));

const totals = (pct: number, before = 1000) => ({
	before_usd: before,
	after_usd: before * (1 + pct / 100),
	delta_usd: (before * pct) / 100,
	delta_pct: pct,
});
const line = (id: string, worst: number, likely: number) => ({
	client_id: id,
	before_usd: 1000,
	cases: { worst: totals(worst), likely: totals(likely), best: totals(5) },
});
const names = { "CL-1": "Alice Tan", "CL-2": "Bo Lim", "CL-3": "Cy Ong" };
const catalogue = {
	status: "computed",
	note: "",
	as_of: "2026-08-26",
	scenarios: [
		{ scenario_id: "s1", name: "Gulf deterioration" },
		{ scenario_id: "s2", name: "Rates higher" },
	],
};
const rollup = (over: Record<string, unknown> = {}) => ({
	scenario_id: "s1",
	status: "computed",
	note: "",
	horizon_months: 3,
	cases: { worst: totals(-8), likely: totals(-3), best: totals(5) },
	most_hit: [line("CL-1", -12, -5), line("CL-2", -6, -1), line("CL-3", -2, 2)],
	beneficiaries: [line("CL-3", -2, 2)],
	crossings: [
		{
			client_id: "CL-1",
			portfolio_id: "PF-1",
			case: "worst",
			kind: "ltv",
			label: "CF-1",
			detail: "CF-1 LTV 70.0% to 80.0% against a trigger of 75%",
		},
	],
	coverage: { computed: 3, total: 3, missing: [] },
	summary: "The most affected client is [[CL-1]].",
	gaps: [],
	...over,
});

beforeEach(() => {
	state.data = { "/scenarios": catalogue, "/scenarios/s1/rollup": rollup() };
});

describe("ScenarioPanel", () => {
	it("shows the picker, book totals for the three cases and the banner", () => {
		render(<ScenarioPanel names={names} />);
		expect(
			screen.getByRole("tab", { name: "Gulf deterioration" }),
		).toHaveAttribute("aria-selected", "true");
		expect(
			screen.getByRole("tab", { name: "Rates higher" }),
		).toBeInTheDocument();
		for (const c of ["worst", "likely", "best"])
			expect(screen.getByTestId(`case-${c}`)).toBeInTheDocument();
		expect(screen.getByTestId("case-worst")).toHaveTextContent("-8.0%");
		expect(screen.getByTestId("conditional-banner")).toHaveTextContent(
			"over 3 months",
		);
	});

	it("ranks the most affected clients and links each to its scenario tab on the same scenario", () => {
		render(<ScenarioPanel names={names} />);
		const list = within(screen.getByTestId("most-hit"));
		const links = list.getAllByRole("link");
		expect(links.map((l) => l.textContent)).toEqual([
			"Alice Tan",
			"Bo Lim",
			"Cy Ong",
		]);
		expect(links[0]).toHaveAttribute(
			"href",
			"/clients/CL-1?tab=scenarios&scenario=s1",
		);
		expect(list.getByText("-12.0%")).toBeInTheDocument();
	});

	it("lists crossings with the client and the case, and the summary with client names", () => {
		render(<ScenarioPanel names={names} />);
		const x = within(screen.getByTestId("crossings"));
		expect(x.getByText(/Worst case/)).toBeInTheDocument();
		expect(x.getByRole("link", { name: "Alice Tan" })).toBeInTheDocument();
		expect(x.getByText(/LTV 70.0% to 80.0%/)).toBeInTheDocument();
		expect(
			within(screen.getByTestId("rollup-summary")).getByRole("link", {
				name: "Alice Tan",
			}),
		).toBeInTheDocument();
	});

	it("selecting another scenario asks for its roll-up", () => {
		state.data["/scenarios/s2/rollup"] = rollup({
			scenario_id: "s2",
			summary: "Rates summary.",
		});
		render(<ScenarioPanel names={names} />);
		fireEvent.click(screen.getByRole("tab", { name: "Rates higher" }));
		expect(screen.getByText("Rates summary.")).toBeInTheDocument();
	});

	it("states that scenarios have not been run when there is no roll-up", () => {
		state.data["/scenarios/s1/rollup"] = rollup({
			status: "placeholder",
			cases: {},
			most_hit: [],
			beneficiaries: [],
			crossings: [],
			summary: "",
		});
		render(<ScenarioPanel names={names} />);
		expect(
			screen.getByText(/Scenarios have not been run for this date/),
		).toBeInTheDocument();
		expect(screen.queryByTestId("case-range")).toBeNull();
	});
});

describe("RollupView", () => {
	it("is honest about partial coverage and names the missing clients", () => {
		render(
			<RollupView
				names={names}
				rollup={
					rollup({
						status: "partial",
						coverage: { computed: 2, total: 3, missing: ["CL-3"] },
					}) as never
				}
			/>,
		);
		const cov = screen.getByTestId("coverage");
		expect(cov).toHaveTextContent("2 of 3 clients covered");
		expect(cov).toHaveTextContent("Not in these totals: Cy Ong");
		expect(screen.getByTestId("partial-notice")).toBeInTheDocument();
	});

	it("shows the first five clients and the rest on request", () => {
		const many = Array.from({ length: 8 }, (_, i) =>
			line(`CL-${i + 10}`, -i - 1, 0),
		);
		render(
			<RollupView
				names={{}}
				rollup={rollup({ most_hit: many, beneficiaries: [] }) as never}
			/>,
		);
		const t = within(screen.getByTestId("most-hit"));
		expect(t.getAllByRole("row")).toHaveLength(6);
		fireEvent.click(t.getByRole("button", { name: "Show all 8 clients" }));
		expect(t.getAllByRole("row")).toHaveLength(9);
	});

	it("shows the gap text of an insufficient roll-up instead of figures", () => {
		render(
			<RollupView
				names={names}
				rollup={
					rollup({
						status: "insufficient_data",
						note: "Insufficient data: no client has a computed result.",
						cases: {},
					}) as never
				}
			/>,
		);
		expect(
			screen.getByText(
				/Scenarios have not been run for this date\. Insufficient data/,
			),
		).toBeInTheDocument();
	});
});
