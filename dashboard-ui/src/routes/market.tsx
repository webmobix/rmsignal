import { createFileRoute } from "@tanstack/react-router";
import { MarketPage } from "#/features/market/MarketPage";

export const Route = createFileRoute("/market")({ component: MarketPage });
