import { useParams } from "@tanstack/react-router";
import { useState } from "react";
import type { Schemas } from "#/api/client";
import { useData } from "#/api/queries";
import { BandsChart } from "#/components/charts/BandsChart";
import { LineTrend } from "#/components/charts/LineTrend";
import {
	createColumnHelper,
	DataTable,
	type tableFeaturesConfig,
} from "#/components/DataTable";
import { IdLink } from "#/components/IdLink";
import { MetricStrip } from "#/components/MetricStrip";
import { PageHeader } from "#/components/PageHeader";
import { EmptyNotice, StateBoundary } from "#/components/StateBoundary";
import { Tabs } from "#/components/Tabs";
import { fmtDate, fmtPct, fmtUsd } from "#/lib/format";
import { MandateStatus } from "../clients/PortfolioList";
import { BreachSection } from "./BreachSection";
import { CallSheet } from "./CallSheet";
import { SectorSection } from "./SectorSection";

type Detail = Schemas["PortfolioDetail"];
type Holding = Detail["holdings"][number];

const helper = createColumnHelper<typeof tableFeaturesConfig, Holding>();
const columns = helper.columns([
	helper.accessor("instrument_name", {
		header: "Instrument",
		cell: ({ row }) => (
			<div>
				<IdLink id={row.original.instrument_id}>
					{row.original.instrument_name}
				</IdLink>
				<div className="num text-xs text-ink-muted">
					{row.original.instrument_id}
				</div>
			</div>
		),
	}),
	helper.accessor("asset_class", { header: "Asset class" }),
	helper.accessor("weight_pct", {
		header: "Weight",
		cell: ({ row }) => (
			<span className="num">{fmtPct(row.original.weight_pct)}</span>
		),
	}),
	helper.accessor("market_value_usd", {
		header: "Value",
		cell: ({ row }) => (
			<span className="num">{fmtUsd(row.original.market_value_usd)}</span>
		),
	}),
	helper.accessor("unrealised_pnl_pct", {
		header: "Unrealised P&L",
		cell: ({ row }) => {
			const v = row.original.unrealised_pnl_pct;
			return (
				<span className={`num ${v != null && v < 0 ? "text-alert" : ""}`}>
					{v == null ? "n/a" : fmtPct(v, 1, true)}
				</span>
			);
		},
	}),
	helper.accessor("liquidity_tier", { header: "Liquidity" }),
]);

export function bandStatement(b: Detail["bands"][number]): string | null {
	if (!b.out_of_band) return null;
	const over = b.weight_pct > b.max_pct;
	const limit = over ? b.max_pct : b.min_pct;
	return `${b.asset_class}: weight ${fmtPct(b.weight_pct)} is ${Math.abs(b.weight_pct - limit).toFixed(1)}pp ${over ? "above the maximum" : "below the minimum"} of ${fmtPct(limit)}.`;
}

export function PortfolioPage() {
	const { portfolioId } = useParams({ from: "/portfolios/$portfolioId" });
	const query = useData<Detail>(`/portfolios/${portfolioId}`);
	const d = query.data;
	const [tab, setTab] = useState("portfolio");
	return (
		<>
			<PageHeader
				eyebrow={`Portfolio · ${portfolioId}`}
				title={d?.portfolio.portfolio_name ?? portfolioId}
				lede={
					d ? (
						<>
							Client <IdLink id={d.client_id}>{d.client_name}</IdLink> ·{" "}
							{d.portfolio.mandate_name || "No mandate"} ·{" "}
							{d.portfolio.service_model} · base currency{" "}
							{d.portfolio.base_currency}
							{d.benchmark ? ` · benchmark ${d.benchmark}` : ""}
							{d.inception_date ? ` · since ${fmtDate(d.inception_date)}` : ""}
						</>
					) : undefined
				}
			/>
			<div className="mt-6">
				<Tabs
					tabs={[
						{ id: "portfolio", label: "Portfolio" },
						{ id: "call-sheet", label: "Call sheet" },
					]}
					value={tab}
					onChange={setTab}
				/>
			</div>
			{tab === "call-sheet" ? <CallSheet portfolioId={portfolioId} /> : null}
			{tab === "portfolio" ? (
				<StateBoundary query={query} label="Loading portfolio">
					{(p) => {
						const statements = p.bands
							.map(bandStatement)
							.filter((s): s is string => s !== null);
						return (
							<div data-testid="portfolio-page">
								<MetricStrip
									metrics={[
										{
											key: "aum",
											label: "AuM",
											value: fmtUsd(p.portfolio.aum_usd),
										},
										{
											key: "change",
											label: "Since previous snapshot",
											value: fmtPct(p.portfolio.change_pct, 1, true),
											hint: fmtUsd(p.portfolio.change_usd),
										},
										{
											key: "mandate",
											label: "Mandate status",
											value: (
												<MandateStatus
													status={p.portfolio.mandate_status}
													breaches={p.portfolio.breach_count}
													reconciliation={p.portfolio.breach_reconciliation}
												/>
											),
										},
										{
											key: "holdings",
											label: "Holdings",
											value: p.holdings.length,
										},
									]}
								/>
								<section className="mt-10" aria-labelledby="pf-hist">
									<h2 id="pf-hist" className="mb-3 text-xl">
										AuM history
									</h2>
									<LineTrend
										points={p.aum_history.map((h) => ({
											date: h.snapshot_date,
											value: h.aum_usd,
										}))}
										ariaLabel="Portfolio AuM over time"
										yLabel="AuM (USD)"
										format={(v) => `${(v / 1e6).toFixed(0)}M`}
									/>
								</section>
								<section className="mt-10" aria-labelledby="bands-h">
									<h2 id="bands-h" className="mb-3 text-xl">
										Mandate bands
									</h2>
									{p.bands.length ? (
										<>
											<BandsChart bands={p.bands} />
											{statements.length ? (
												<ul
													className="mt-3 space-y-1 font-medium text-alert"
													data-testid="band-breaches"
												>
													{statements.map((s) => (
														<li key={s}>{s}</li>
													))}
												</ul>
											) : (
												<p className="mt-3 text-positive">
													All asset classes are within their bands.
												</p>
											)}
										</>
									) : (
										<EmptyNotice>
											{p.position_limit?.note ||
												"No mandate bands apply to this portfolio."}
										</EmptyNotice>
									)}
									{p.position_limit &&
									p.position_limit.max_single_position_pct != null ? (
										<p className="mt-3 text-ink-2">
											Largest position{" "}
											<IdLink
												id={p.position_limit.largest_instrument_id ?? ""}
											/>{" "}
											at{" "}
											<span className="num">
												{fmtPct(p.position_limit.largest_weight_pct)}
											</span>{" "}
											against a single-position limit of{" "}
											<span className="num">
												{fmtPct(p.position_limit.max_single_position_pct)}
											</span>
											{p.position_limit.breaches.length ? (
												<b className="text-alert"> (breached)</b>
											) : null}
											.
										</p>
									) : null}
								</section>
								<BreachSection
									exclusions={p.exclusion_breaches}
									reconciliation={p.breach_reconciliation}
								/>
								<section className="mt-10" aria-labelledby="sector-h">
									<h2 id="sector-h" className="mb-3 text-xl">
										Sector exposure
									</h2>
									<SectorSection exposure={p.sector_exposure} />
								</section>
								<section className="mt-10" aria-labelledby="hold-h">
									<h2 id="hold-h" className="mb-3 text-xl">
										Holdings
									</h2>
									<DataTable
										columns={columns}
										data={p.holdings}
										initialSort={{ id: "weight_pct", desc: true }}
										rowId={(h) => h.instrument_id}
									/>
								</section>
								{p.facilities.map((f) => (
									<section
										key={f.facility_id}
										className="mt-10"
										aria-labelledby={`ltv-${f.facility_id}`}
									>
										<h2 id={`ltv-${f.facility_id}`} className="mb-3 text-xl">
											Loan-to-value · {f.facility_type}
										</h2>
										<LineTrend
											points={f.history.map((h) => ({
												date: h.snapshot_date,
												value: h.ltv_pct,
											}))}
											ariaLabel={`LTV history for ${f.facility_id}`}
											yLabel="LTV (%)"
											rule={{
												value: f.margin_call_ltv_pct,
												label: `Margin-call trigger ${f.margin_call_ltv_pct}%`,
											}}
										/>
									</section>
								))}
							</div>
						);
					}}
				</StateBoundary>
			) : null}
		</>
	);
}
