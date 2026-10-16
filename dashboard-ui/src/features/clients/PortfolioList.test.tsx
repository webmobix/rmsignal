import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MandateStatus } from "./PortfolioList";

describe("MandateStatus with reconciliation", () => {
	it("shows a claimed waiver and keeps the breach as out of band", () => {
		render(
			<MandateStatus
				status="out_of_band"
				breaches={1}
				reconciliation={
					[
						{
							status: "client_directed",
							note_ids: ["N-010"],
							waiver_claimed: true,
						},
					] as never
				}
			/>,
		);
		expect(screen.getByText(/Out of band/)).toBeInTheDocument();
		expect(screen.getByTestId("breach-label")).toHaveTextContent(
			"waiver claimed (N-010)",
		);
	});
	it("shows no label for no_note", () => {
		render(
			<MandateStatus
				status="out_of_band"
				breaches={1}
				reconciliation={[{ status: "no_note", note_ids: [] }] as never}
			/>,
		);
		expect(screen.getByText(/Out of band/)).toBeInTheDocument();
		expect(screen.queryByTestId("breach-label")).toBeNull();
	});
	it("never labels a portfolio that is within its mandate", () => {
		render(
			<MandateStatus
				status="in_band"
				reconciliation={
					[{ status: "acknowledged", note_ids: ["N-001"] }] as never
				}
			/>,
		);
		expect(screen.queryByTestId("breach-label")).toBeNull();
	});
});
