import { createFileRoute } from "@tanstack/react-router";
import { PortfolioPage } from "#/features/portfolios/PortfolioPage";

export const Route = createFileRoute("/portfolios/$portfolioId")({
	component: PortfolioPage,
});
