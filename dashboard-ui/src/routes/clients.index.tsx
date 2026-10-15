import { createFileRoute } from "@tanstack/react-router";
import { ClientsPage } from "#/features/clients/ClientsPage";

export const Route = createFileRoute("/clients/")({ component: ClientsPage });
