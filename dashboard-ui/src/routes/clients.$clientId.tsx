import { createFileRoute } from "@tanstack/react-router";
import { ClientPage } from "#/features/clients/ClientPage";

export const Route = createFileRoute("/clients/$clientId")({
	component: ClientPage,
});
