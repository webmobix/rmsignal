import { createFileRoute } from "@tanstack/react-router";
import { ActionsPage } from "#/features/actions/ActionsPage";

export const Route = createFileRoute("/actions")({
	component: ActionsPage,
	validateSearch: (search: Record<string, unknown>): { tier?: string } => ({
		tier: typeof search.tier === "string" ? search.tier : undefined,
	}),
});
