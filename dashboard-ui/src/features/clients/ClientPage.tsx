import { getRouteApi, useParams } from "@tanstack/react-router";
import { useState } from "react";
import type { Schemas } from "#/api/client";
import { useData } from "#/api/queries";
import { PageHeader } from "#/components/PageHeader";
import { StateBoundary } from "#/components/StateBoundary";
import { Tabs } from "#/components/Tabs";
import { fmtDate } from "#/lib/format";
import { ScenarioTab } from "../scenarios/ScenarioTab";
import { ActionsNotes } from "./ActionsNotes";
import { Health } from "./Health";
import { PortfolioList } from "./PortfolioList";
import { SnapshotCompare } from "./SnapshotCompare";
import { ClientSummary } from "./Summary";

type Detail = Schemas["ClientDetail"];

const route = getRouteApi("/clients/$clientId");

export function ClientPage() {
	const { clientId } = useParams({ from: "/clients/$clientId" });
	const search = route.useSearch();
	const [tab, setTab] = useState(search.tab ?? "summary");
	const query = useData<Detail>(`/clients/${clientId}`);
	const history = useData<Schemas["AumHistory"]>(
		`/clients/${clientId}/aum-history`,
	);
	const dates = history.data?.total.map((t) => t.snapshot_date) ?? [];
	const p = query.data?.profile;
	return (
		<>
			<PageHeader
				eyebrow={`Client · ${clientId}`}
				title={p?.client_name ?? clientId}
				lede={
					p
						? `${p.wealth_band} · ${p.risk_profile} risk profile · ${p.booking_centre} booking centre · base currency ${p.base_currency} · client since ${fmtDate(p.client_since)}`
						: undefined
				}
			/>
			<StateBoundary query={query} label="Loading client">
				{(detail) => (
					<>
						<Tabs
							value={tab}
							onChange={setTab}
							tabs={[
								{ id: "summary", label: "Summary and portfolios" },
								{ id: "actions", label: "Actions and notes" },
								{ id: "compare", label: "Compare snapshots" },
								{ id: "scenarios", label: "Scenarios" },
							]}
						/>
						{tab === "summary" ? (
							<>
								<ClientSummary detail={detail}>
									<Health detail={detail} />
								</ClientSummary>
								<PortfolioList portfolios={detail.portfolios} />
							</>
						) : null}
						{tab === "actions" ? <ActionsNotes detail={detail} /> : null}
						{tab === "compare" ? (
							<SnapshotCompare clientId={clientId} dates={dates} />
						) : null}
						{tab === "scenarios" ? (
							<ScenarioTab
								clientId={clientId}
								initialScenario={search.scenario}
							/>
						) : null}
					</>
				)}
			</StateBoundary>
		</>
	);
}
