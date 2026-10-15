import { createFileRoute } from "@tanstack/react-router";
import { InstrumentPage } from "#/features/instruments/InstrumentPage";

export const Route = createFileRoute("/instruments/$instrumentId")({
	component: InstrumentPage,
});
