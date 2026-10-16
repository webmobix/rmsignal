import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "#/api/client";

const state: { callSheet: "error" | "loading" } = { callSheet: "error" };

vi.mock("@tanstack/react-router", () => ({
	useParams: () => ({ portfolioId: "PF-0009" }),
	Link: ({ children }: { children: React.ReactNode }) => (
		<a href="/x">{children}</a>
	),
}));
vi.mock("#/components/IdLink", () => ({
	IdLink: ({ id, children }: { id: string; children?: React.ReactNode }) => (
		<a href={`#${id}`}>{children ?? id}</a>
	),
}));
vi.mock("#/components/charts/BandsChart", () => ({
	BandsChart: () => <div />,
}));
vi.mock("#/components/charts/LineTrend", () => ({ LineTrend: () => <div /> }));
vi.mock("./SectorSection", () => ({ SectorSection: () => <div /> }));
vi.mock("#/api/queries", () => ({
	useAsOf: () => "2026-08-26",
	useData: (path: string) => {
		if (path.endsWith("/call-sheet"))
			return state.callSheet === "error"
				? {
						isError: true,
						error: new ApiError(500, "call sheet unavailable"),
						isPending: false,
						data: undefined,
						refetch: vi.fn(),
					}
				: {
						isError: false,
						isPending: true,
						data: undefined,
						refetch: vi.fn(),
					};
		return {
			isError: false,
			isPending: false,
			refetch: vi.fn(),
			data: {
				gaps: [],
				portfolio: {
					portfolio_name: "Core Balanced",
					mandate_name: "Balanced",
					service_model: "Discretionary",
					base_currency: "USD",
					aum_usd: 1,
					change_pct: 0,
					change_usd: 0,
					mandate_status: "in_band",
					breach_count: 0,
					breach_reconciliation: [],
				},
				client_id: "CL-0007",
				client_name: "Client Seven",
				benchmark: "",
				inception_date: "",
				aum_history: [],
				bands: [],
				position_limit: { breaches: [], note: "" },
				exclusion_breaches: [],
				breach_reconciliation: [],
				holdings: [],
				sector_exposure: { direct: [], look_through: [] },
				facilities: [],
			},
		};
	},
}));

import { PortfolioPage } from "./PortfolioPage";

describe("portfolio tabs", () => {
	it("keeps the portfolio tab working when the call sheet request fails", () => {
		render(<PortfolioPage />);
		expect(screen.getByTestId("portfolio-page")).toBeInTheDocument();
		fireEvent.click(screen.getByRole("tab", { name: "Call sheet" }));
		expect(screen.getByRole("alert")).toHaveTextContent(
			"call sheet unavailable",
		);
		expect(screen.queryByTestId("portfolio-page")).toBeNull();
		fireEvent.click(screen.getByRole("tab", { name: "Portfolio" }));
		expect(screen.getByTestId("portfolio-page")).toBeInTheDocument();
		expect(screen.queryByRole("alert")).toBeNull();
	});
	it("shows a loading state while the call sheet loads", () => {
		state.callSheet = "loading";
		render(<PortfolioPage />);
		fireEvent.click(screen.getByRole("tab", { name: "Call sheet" }));
		expect(screen.getByText(/Loading call sheet/)).toBeInTheDocument();
		state.callSheet = "error";
	});
});
