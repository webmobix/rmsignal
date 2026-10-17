import { useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import type { Schemas } from "#/api/client";
import { useData } from "#/api/queries";
import { BarList } from "#/components/charts/BarList";
import {
	createColumnHelper,
	DataTable,
	type tableFeaturesConfig,
} from "#/components/DataTable";
import { IdLink } from "#/components/IdLink";
import { MetricStrip } from "#/components/MetricStrip";
import { PageHeader } from "#/components/PageHeader";
import { StateBoundary } from "#/components/StateBoundary";
import { TierBadge } from "#/components/TierBadge";
import { fmtDate, fmtUsd, titleCase } from "#/lib/format";

type Row = Schemas["ClientRow"];
const helper = createColumnHelper<typeof tableFeaturesConfig, Row>();

const columns = helper.columns([
	helper.accessor("client_name", {
		header: "Client",
		cell: ({ row }) => (
			<div>
				<IdLink id={row.original.client_id}>{row.original.client_name}</IdLink>
				<div className="num text-xs text-ink-muted">
					{row.original.client_id}
				</div>
			</div>
		),
	}),
	helper.accessor("aum_usd", {
		header: "AuM",
		cell: ({ row }) => (
			<span className="num">{fmtUsd(row.original.aum_usd)}</span>
		),
	}),
	helper.accessor("wealth_band", { header: "Wealth band" }),
	helper.accessor("risk_profile", { header: "Risk profile" }),
	helper.accessor("portfolio_count", {
		header: "Portfolios",
		cell: ({ row }) => (
			<span className="num">{row.original.portfolio_count}</span>
		),
	}),
	helper.accessor("action_count", {
		header: "Actions",
		cell: ({ row }) => <span className="num">{row.original.action_count}</span>,
	}),
	helper.accessor("top_importance", {
		header: "Top tier",
		cell: ({ row }) => <TierBadge tier={row.original.top_importance} />,
	}),
	helper.accessor("report_status", {
		header: "Report",
		cell: ({ row }) => titleCase(row.original.report_status),
	}),
	helper.accessor("kyc_review_due", {
		header: "KYC due",
		cell: ({ row }) => (
			<span
				className={`num ${row.original.kyc_overdue ? "font-semibold text-alert" : ""}`}
			>
				{fmtDate(row.original.kyc_review_due)}
				{row.original.kyc_overdue ? " · overdue" : ""}
			</span>
		),
	}),
]);

export function ClientsPage() {
	const query = useData<Row[]>("/clients");
	const navigate = useNavigate();
	const [order, setOrder] = useState<Row[]>([]);
	const rows = useMemo(() => query.data ?? [], [query.data]);
	const chartRows = (order.length ? order : rows).map((r) => ({
		key: r.client_id,
		label: r.client_name,
		value: r.aum_usd,
	}));
	return (
		<>
			<PageHeader eyebrow="Clients" title="Your book, client by client" />
			<StateBoundary query={query} label="Loading clients">
				{() => (
					<>
						<MetricStrip
							metrics={[
								{ key: "clients", label: "Clients", value: rows.length },
								{
									key: "aum",
									label: "Assets under management",
									value: fmtUsd(rows.reduce((s, r) => s + r.aum_usd, 0)),
								},
								{
									key: "portfolios",
									label: "Portfolios",
									value: rows.reduce((s, r) => s + r.portfolio_count, 0),
								},
							]}
						/>
						<div className="mt-8">
							<DataTable
								columns={columns}
								data={rows}
								initialSort={{ id: "aum_usd", desc: true }}
								onSortChange={setOrder}
								rowId={(r) => r.client_id}
							/>
						</div>
						<section className="mt-10" aria-labelledby="aum-h">
							<h2 id="aum-h" className="mb-3 text-2xl">
								AuM by client
							</h2>
							<BarList
								rows={chartRows}
								ariaLabel="Assets under management by client"
								valueLabel="AuM (USD)"
								onSelect={(r) =>
									navigate({
										to: "/clients/$clientId",
										params: { clientId: r.key },
									})
								}
							/>
						</section>
					</>
				)}
			</StateBoundary>
		</>
	);
}
