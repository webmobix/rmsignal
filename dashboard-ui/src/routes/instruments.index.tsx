import { createFileRoute } from "@tanstack/react-router";
import { InstrumentsPage } from "#/features/instruments/InstrumentsPage";

export const Route = createFileRoute("/instruments/")({
	component: InstrumentsPage,
});
