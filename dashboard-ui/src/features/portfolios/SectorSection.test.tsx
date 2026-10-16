import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SectorSection } from "./SectorSection";

vi.mock("#/components/charts/SectorChart", () => ({
	SectorChart: ({ groups }: { groups: { name: string }[] }) => (
		<div data-testid="chart">{groups.map((g) => g.name).join("|")}</div>
	),
}));

const exposure = {
	denominator: 100,
	denominator_label: "portfolio value in base currency",
	direct: [
		{
			name: "Diversified",
			value: 60,
			exposure_pct: 60,
			positions: 1,
			contributors: [],
		},
		{
			name: "Energy",
			value: 40,
			exposure_pct: 40,
			positions: 1,
			contributors: [],
		},
	],
	look_through: [
		{
			name: "Energy",
			value: 70,
			exposure_pct: 70,
			positions: 1,
			contributors: ["SP"],
		},
		{
			name: "Unclassified (look-through)",
			value: 30,
			exposure_pct: 30,
			positions: 0,
			contributors: ["SP"],
		},
	],
	basket_attribution_assumption: true,
} as never;

describe("SectorSection", () => {
	it("shows the direct view first and switches data on toggle", () => {
		render(<SectorSection exposure={exposure} />);
		expect(screen.getByTestId("chart")).toHaveTextContent("Diversified|Energy");
		expect(screen.queryByTestId("sector-unclassified")).toBeNull();
		fireEvent.click(screen.getByRole("tab", { name: "Look-through" }));
		expect(screen.getByTestId("chart")).toHaveTextContent(
			"Energy|Unclassified (look-through)",
		);
		expect(screen.getByTestId("sector-unclassified")).toHaveTextContent(
			"30.0%",
		);
		expect(screen.getByText(/split equally/)).toBeInTheDocument();
	});
	it("notes asset-type labels and that no sector limit applies", () => {
		render(<SectorSection exposure={exposure} />);
		expect(screen.getByTestId("sector-notes")).toHaveTextContent(
			/Diversified is an asset-type label/,
		);
		expect(screen.getByTestId("sector-notes")).toHaveTextContent(
			/no sector limits/,
		);
	});
	it("shows the empty state without positions", () => {
		render(
			<SectorSection
				exposure={
					{ ...(exposure as object), direct: [], look_through: [] } as never
				}
			/>,
		);
		expect(screen.getByText(/No positions to show/)).toBeInTheDocument();
		expect(screen.queryByTestId("chart")).toBeNull();
	});
});
