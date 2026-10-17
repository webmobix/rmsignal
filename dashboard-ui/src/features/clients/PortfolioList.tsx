import type { Schemas } from "#/api/client";
import {
	createColumnHelper,
	DataTable,
	type tableFeaturesConfig,
} from "#/components/DataTable";
import { IdLink } from "#/components/IdLink";
import { fmtPct, fmtUsd } from "#/lib/format";
import { MANDATE_LABEL, worstBreachLabel } from "./status";

type Row = Schemas["ClientDetail"]["portfolios"][number];
const helper = createColumnHelper<typeof tableFeaturesConfig, Row>();

export function MandateStatus({
	status,
	breaches,
	reconciliation,
}: {
	status: string;
	breaches?: number;
	reconciliation?: Row["breach_reconciliation"];
}) {
	const label =
		status === "out_of_band" ? worstBreachLabel(reconciliation) : null;
	const tone =
		status === "out_of_band"
			? "text-alert"
			: status === "no_mandate"
				? "text-ink-muted"
				: "text-positive";
	return (
		<span className={`text-xs font-semibold ${tone}`}>
			{MANDATE_LABEL[status] ?? status}
			{status === "out_of_band" && breaches ? ` · ${breaches}` : ""}
			{label ? (
				<span className="font-medium text-ink-2" data-testid="breach-label">
					{" · "}
					{label}
				</span>
			) : null}
		</span>
	);
}

const columns = helper.columns([
	helper.accessor("portfolio_name", {
		header: "Portfolio",
		cell: ({ row }) => (
			<div>
				<IdLink id={row.original.portfolio_id}>
					{row.original.portfolio_name}
				</IdLink>
				<div className="num text-xs text-ink-muted">
					{row.original.portfolio_id}
				</div>
			</div>
		),
	}),
	helper.accessor("mandate_name", {
		header: "Mandate",
		cell: ({ row }) => row.original.mandate_name || "None",
	}),
	helper.accessor("service_model", { header: "Service model" }),
	helper.accessor("aum_usd", {
		header: "AuM",
		cell: ({ row }) => (
			<span className="num">{fmtUsd(row.original.aum_usd)}</span>
		),
	}),
	helper.accessor("change_pct", {
		header: "Since previous",
		cell: ({ row }) => (
			<span className="num">
				{fmtPct(row.original.change_pct, 1, true)}{" "}
				<span className="text-ink-muted">
					({fmtUsd(row.original.change_usd)})
				</span>
			</span>
		),
	}),
	helper.accessor("mandate_status", {
		header: "Mandate status",
		cell: ({ row }) => (
			<MandateStatus
				status={row.original.mandate_status}
				breaches={row.original.breach_count}
				reconciliation={row.original.breach_reconciliation}
			/>
		),
	}),
]);

export function PortfolioList({ portfolios }: { portfolios: Row[] }) {
	return (
		<section aria-labelledby="pf-h" className="mt-10">
			<h2 id="pf-h" className="mb-3 text-2xl">
				Portfolios
			</h2>
			<div data-testid="portfolio-list">
				<DataTable
					columns={columns}
					data={portfolios}
					rowId={(r) => r.portfolio_id}
				/>
			</div>
		</section>
	);
}
