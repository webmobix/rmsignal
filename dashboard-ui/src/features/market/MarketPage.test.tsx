import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EventItem } from "./MarketPage";

vi.mock("#/components/IdLink", () => ({
	IdLink: ({ id, children }: { id: string; children?: React.ReactNode }) => (
		<a href={`#${id}`}>{children ?? id}</a>
	),
}));

const event = {
	event_date: "2026-08-05",
	event_type: "Geopolitical",
	region: "Middle East",
	description: "Naval blockade.",
	severity: "Severe",
	primary_transmission: "Energy, shipping",
	reach: {
		derived: true,
		matched_channels: ["Energy"],
		unmatched_channels: ["shipping"],
		clients: [
			{ client_id: "CL-0001", client_name: "Hartono", held_usd: 24_900_000 },
		],
		instruments: [
			{
				instrument_id: "SYN-EQ-0002",
				instrument_name: "Energy Fund",
				held_usd: 17_300_000,
			},
		],
	},
} as never;

describe("EventItem", () => {
	it("labels reach as derived and links clients and instruments", () => {
		render(<EventItem event={event} />);
		expect(screen.getByText(/\(derived\)/)).toBeInTheDocument();
		expect(screen.getByRole("link", { name: "Hartono" })).toHaveAttribute(
			"href",
			"#CL-0001",
		);
		expect(screen.getByRole("link", { name: "Energy Fund" })).toHaveAttribute(
			"href",
			"#SYN-EQ-0002",
		);
		expect(screen.getByText(/Not matched: shipping/)).toBeInTheDocument();
	});
});
