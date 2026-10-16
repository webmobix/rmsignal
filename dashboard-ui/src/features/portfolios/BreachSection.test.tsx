import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BreachSection } from "./BreachSection";

vi.mock("#/components/IdLink", () => ({
	IdLink: ({ id }: { id: string }) => <span>{id}</span>,
}));

const note = {
	note_id: "N-010",
	note_date: "2026-01-22",
	quote:
		"Client instructed an additional gold purchase. Suitability waiver on file.",
};
const claimed = {
	portfolio_id: "PF-0009",
	kind: "band",
	key: "Commodities",
	status: "client_directed",
	note_ids: ["N-010"],
	description: "Commodities weight is 14.20% against a maximum of 10.00%",
	rationale: "r",
	waiver_claimed: true,
	notes: [note],
};
const plain = {
	...claimed,
	key: "Fixed Income",
	status: "no_note",
	note_ids: [],
	notes: [],
	waiver_claimed: false,
	description: "Fixed Income weight is 60.00% against a maximum of 50.00%",
};
const exclusion = {
	instrument_id: "SYN-EQ-0008",
	instrument_name: "Global Energy Majors Equity Fund",
	held: "direct",
	value: 1,
	weight_pct: 11.1,
	key: "SYN-EQ-0008",
	status: "contradicted",
	note_ids: ["N-008"],
};

describe("BreachSection", () => {
	it("quotes the note and says the waiver is a claim, with the breach still marked", () => {
		render(
			<BreachSection
				exclusions={[]}
				reconciliation={[claimed, plain] as never}
			/>,
		);
		const notes = screen.getByTestId("breach-notes");
		expect(notes).toHaveTextContent("Commodities weight is 14.20%");
		expect(notes).toHaveTextContent("waiver claimed (N-010)");
		expect(notes).toHaveTextContent(/Suitability waiver on file/);
		expect(notes).toHaveTextContent(/not verified; the breach stays flagged/);
		expect(notes).not.toHaveTextContent("Fixed Income");
	});
	it("lists an exclusion breach with its weight and status", () => {
		render(
			<BreachSection exclusions={[exclusion] as never} reconciliation={[]} />,
		);
		const list = screen.getByTestId("exclusion-breaches");
		expect(list).toHaveTextContent("Exclusion breach");
		expect(list).toHaveTextContent("Global Energy Majors Equity Fund");
		expect(list).toHaveTextContent("11.1%");
		expect(list).toHaveTextContent("contradicted (N-008)");
	});
	it("shows an exclusion breach without a note as plain", () => {
		render(
			<BreachSection
				exclusions={
					[{ ...exclusion, status: "no_note", note_ids: [] }] as never
				}
				reconciliation={[]}
			/>,
		);
		expect(screen.getByTestId("exclusion-breaches")).not.toHaveTextContent("·");
	});
	it("renders nothing without breaches or notes", () => {
		const { container } = render(
			<BreachSection exclusions={[]} reconciliation={[plain] as never} />,
		);
		expect(container).toBeEmptyDOMElement();
	});
});
