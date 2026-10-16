import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CallSheetBody } from "./CallSheet";
import { BankViewCard, MandateCard } from "./callsheetSections";

vi.mock("@tanstack/react-router", () => ({
	Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
		<a href={to}>{children}</a>
	),
}));
vi.mock("#/components/IdLink", () => ({
	IdLink: ({ id }: { id: string }) => <a href={`#${id}`}>{id}</a>,
}));
vi.mock("./SectorSection", () => ({
	SectorSection: () => <div data-testid="sector-section" />,
}));

const view = (
	direction: string,
	rationale = "Rates are expected to ease.",
) => ({
	direction,
	horizon: "3m",
	confidence: "medium",
	rationale,
	drivers: [
		{ claim: "Policy rate path", evidence_ids: ["ev_1"], event_refs: [] },
	],
	risks: [],
	would_change_if: "",
	change: { kind: "unchanged", why: "" },
});

const entries = [
	{
		instrument_id: "SYN-EQ-0001",
		instrument_name: "Global Equity Fund",
		asset_class: "Equity",
		weight_pct: 40,
		value_usd: 100,
		outlook: {
			as_of: "2026-08-26",
			older_than_as_of: false,
			view: view("positive"),
			market_outlook_as_of: "2026-08-26",
			market_context: [
				{
					segment: "equity",
					direction: "positive",
					horizon: "3m",
					confidence: "high",
				},
			],
		},
	},
	{
		instrument_id: "SYN-FI-0002",
		instrument_name: "Bond Fund",
		asset_class: "Fixed Income",
		weight_pct: 30,
		value_usd: 70,
		outlook: {
			as_of: "2026-06-30",
			older_than_as_of: true,
			view: view("neutral"),
			market_outlook_as_of: null,
			market_context: [],
		},
	},
	{
		instrument_id: "SYN-CM-0003",
		instrument_name: "Gold ETF",
		asset_class: "Commodities",
		weight_pct: 10,
		value_usd: 20,
		outlook: null,
	},
];

const claimed = {
	portfolio_id: "PF-0009",
	kind: "band",
	key: "Commodities",
	status: "client_directed",
	note_ids: ["N-010"],
	description: "Commodities weight is 18.93% against a maximum of 10.00%",
	rationale: "r",
	waiver_claimed: true,
	notes: [
		{
			note_id: "N-010",
			note_date: "2026-01-22",
			quote:
				"Client instructed an additional gold purchase. Suitability waiver on file.",
		},
	],
};

const sheet = {
	as_of: "2026-08-26",
	snapshot_date: "2026-08-26",
	portfolio_id: "PF-0009",
	portfolio_name: "Core Balanced",
	client_id: "CL-0007",
	client_name: "Client Seven",
	mandate_name: "Balanced",
	service_model: "Discretionary",
	performance: {
		gaps: [],
		aum_usd: 4e7,
		previous_aum_usd: 4.1e7,
		change_usd: -1e6,
		change_pct: -2.4,
		previous_snapshot_date: "2026-06-30",
		snapshot_date: "2026-08-26",
		contributors: [
			{
				instrument_id: "SYN-CM-0003",
				instrument_name: "Gold ETF",
				value_usd_from: 5,
				value_usd_to: 4,
				change_usd: -1e5,
			},
		],
		findings: [],
		events: [],
	},
	mandate: {
		gaps: [],
		applicable: true,
		statement: "Balanced mandate",
		bands: [
			{
				asset_class: "Commodities",
				weight_pct: 18.9,
				min_pct: 0,
				target_pct: 3,
				max_pct: 10,
				gap_pp: 8.9,
				breach: "above_max",
				out_of_band: true,
			},
		],
		position_limit: { breaches: [], note: "" },
		exclusion_breaches: [],
		breach_reconciliation: [claimed],
		open_actions: [],
	},
	ownership: {
		gaps: [
			{
				kind: "other",
				description: "underlying 'XAU spot' matches no instrument",
			},
		],
		sector_exposure: { direct: [], look_through: [] },
		unclassified_pct: { direct: 0, look_through: 0 },
	},
	bank_view: { gaps: [], entries },
	events: {
		gaps: [],
		events: [
			{
				event_id: "EVT-2026-08-01-1",
				event_date: "2026-08-01",
				event_type: "Market",
				region: "Global",
				description: "Oil falls on supply news",
				severity: "High",
				primary_transmission: "Energy",
				instruments: [
					{
						instrument_id: "SYN-EQ-0008",
						instrument_name: "Energy Fund",
						matched_on: [{ field: "sector", token: "energy" }],
					},
				],
			},
		],
	},
	cash_credit: {
		gaps: [],
		facilities: [],
		client_liquidity: null,
		client_level_note: "Client level",
	},
	conversation: {
		gaps: [],
		notes: [
			{
				note_id: "N-010",
				note_date: "2026-01-22",
				channel: "Call",
				note: "Spoke about gold.",
			},
		],
		note_limit: 10,
		note_total: 1,
		commitments: [],
		scope: "client",
		client_level_note: "Client level",
	},
} as never;

describe("CallSheetBody", () => {
	it("shows the seven questions in order with the as-of date", () => {
		render(<CallSheetBody sheet={sheet} />);
		const headings = screen
			.getAllByRole("heading", { level: 2 })
			.map((h) => h.textContent);
		expect(headings).toEqual([
			"How am I doing?",
			"Am I within my mandate?",
			"What do I own?",
			"What does the bank think?",
			"What is happening?",
			"How are my cash and credit?",
			"When did we last speak?",
		]);
		expect(screen.getByTestId("call-sheet")).toHaveTextContent(
			"as of 26 Aug 2026",
		);
	});
	it("shows a section's gap and renders the other sections normally", () => {
		render(<CallSheetBody sheet={sheet} />);
		const own = screen.getByTestId("cs-ownership");
		expect(within(own).getByTestId("gaps")).toHaveTextContent("XAU spot");
		expect(
			within(screen.getByTestId("cs-bank_view")).queryByTestId("gaps"),
		).toBeNull();
		expect(screen.getAllByTestId("bank-view-row")).toHaveLength(3);
	});
	it("links instruments, events and notes to their views", () => {
		render(<CallSheetBody sheet={sheet} />);
		expect(
			within(screen.getByTestId("bank-view")).getByRole("link", {
				name: "SYN-EQ-0001",
			}),
		).toHaveAttribute("href", "#SYN-EQ-0001");
		expect(
			within(screen.getByTestId("cs-event-list")).getByRole("link", {
				name: "Oil falls on supply news",
			}),
		).toHaveAttribute("href", "/market");
		expect(
			within(screen.getByTestId("cs-notes")).getByRole("link", {
				name: "N-010",
			}),
		).toHaveAttribute("href", "/clients/$clientId");
	});
});

describe("bank view rows", () => {
	it("has a current view, an older view and a no-outlook row, none hidden", () => {
		render(
			<BankViewCard s={{ gaps: [], entries } as never} asOf="2026-08-26" />,
		);
		const [cur, old, none] = screen.getAllByTestId("bank-view-row");
		expect(cur).toHaveTextContent(
			"Bank view as of 26 Aug 2026: positive, 3m horizon, medium confidence",
		);
		expect(cur).not.toHaveTextContent(/older than/);
		expect(cur).toHaveTextContent(
			"Market view as of 26 Aug 2026: equity positive",
		);
		expect(old).toHaveTextContent("Bank view as of 30 Jun 2026");
		expect(old).toHaveTextContent("older than 26 Aug 2026");
		expect(none).toHaveTextContent("no outlook");
	});
	it("uses no recommendation wording", () => {
		const { container } = render(
			<BankViewCard s={{ gaps: [], entries } as never} asOf="2026-08-26" />,
		);
		expect(container.textContent).not.toMatch(
			/\b(buy|sell|recommend\w*|you should|we advise|add to|reduce your)\b/i,
		);
		expect(container.textContent).toMatch(/not advice/);
	});
});

describe("mandate rows", () => {
	it("quotes the note, reads as a claim to verify and keeps the breach marked", () => {
		render(<MandateCard s={(sheet as never as { mandate: never }).mandate} />);
		expect(screen.getByTestId("cs-bands")).toHaveTextContent(
			"Commodities: weight 18.9% against a maximum of 10.0%",
		);
		const notes = screen.getByTestId("breach-notes");
		expect(notes).toHaveTextContent("waiver claimed (N-010)");
		expect(notes).toHaveTextContent(/Suitability waiver on file/);
		expect(notes).toHaveTextContent(/claim to verify/);
		expect(screen.queryByText(/within their bands/)).toBeNull();
	});
	it("says no mandate applies for a custody account", () => {
		render(
			<MandateCard
				s={
					{
						gaps: [],
						applicable: false,
						statement: "Custody account: not measured against a mandate",
						bands: [],
					} as never
				}
			/>,
		);
		expect(
			screen.getByText(/not measured against a mandate/),
		).toBeInTheDocument();
		expect(screen.queryByTestId("cs-bands")).toBeNull();
	});
});

void fireEvent;
