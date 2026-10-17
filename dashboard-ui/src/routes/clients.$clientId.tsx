import { createFileRoute } from "@tanstack/react-router";
import { ClientPage } from "#/features/clients/ClientPage";

export const Route = createFileRoute("/clients/$clientId")({
	component: ClientPage,
	validateSearch: (
		search: Record<string, unknown>,
	): { tab?: string; scenario?: string } => ({
		tab: typeof search.tab === "string" ? search.tab : undefined,
		scenario: typeof search.scenario === "string" ? search.scenario : undefined,
	}),
});
