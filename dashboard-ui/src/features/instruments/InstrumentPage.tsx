import { useParams } from "@tanstack/react-router";
import type { Schemas } from "#/api/client";
import { useData } from "#/api/queries";
import { BarList } from "#/components/charts/BarList";
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
import { ViewCard } from "#/components/ViewCard";
import { fmtDate, fmtPct, fmtUsd, titleCase } from "#/lib/format";

type Detail = Schemas["InstrumentDetail"];
type Holder = Detail["holders"][number];

const helper = createColumnHelper<typeof tableFeaturesConfig, Holder>();
const columns = helper.columns([
	helper.accessor("client_name", {
		header: "Client",
		cell: ({ row }) => (
			<IdLink id={row.original.client_id}>{row.original.client_name}</IdLink>
		),
	}),
	helper.accessor("portfolio_id", {
		header: "Portfolio",
		cell: ({ row }) => <IdLink id={row.original.portfolio_id} />,
	}),
	helper.accessor("quantity", {
		header: "Quantity",
		cell: ({ row }) => (
			<span className="num">
				{row.original.quantity.toLocaleString("en-US")}
			</span>
		),
	}),
	helper.accessor("value_usd", {
		header: "Value",
		cell: ({ row }) => (
			<span className="num">{fmtUsd(row.original.value_usd)}</span>
		),
	}),
	helper.accessor("weight_pct", {
		header: "Weight in portfolio",
		cell: ({ row }) => (
			<span className="num">{fmtPct(row.original.weight_pct)}</span>
		),
	}),
]);

export function perClient(
	holders: Holder[],
): { key: string; label: string; value: number }[] {
	const totals = new Map<string, { label: string; value: number }>();
	for (const h of holders) {
		const cur = totals.get(h.client_id) ?? { label: h.client_name, value: 0 };
		cur.value += h.value_usd;
		totals.set(h.client_id, cur);
	}
	return [...totals.entries()]
		.sort((a, b) => b[1].value - a[1].value)
		.map(([key, v]) => ({ key, ...v }));
}

export function InstrumentPage() {
	const { instrumentId } = useParams({ from: "/instruments/$instrumentId" });
	const query = useData<Detail>(`/instruments/${instrumentId}`);
	const d = query.data;
	return (
		<>
			<PageHeader
				eyebrow={`Instrument · ${instrumentId}`}
				title={d?.instrument.instrument_name ?? instrumentId}
				lede={
					d
						? `${d.instrument.asset_class} · ${d.instrument.sub_asset_class} · ${d.instrument.sector} · ${d.instrument.region} · ${d.instrument.currency} · ${d.instrument.liquidity_tier} liquidity`
						: undefined
				}
			/>
			<StateBoundary query={query} label="Loading instrument">
				{(i) => (
					<div data-testid="instrument-page">
						<MetricStrip
							metrics={[
								{
									key: "price",
									label: "Latest price",
									value:
										i.instrument.latest_price?.toLocaleString("en-US", {
											maximumFractionDigits: 2,
										}) ?? "n/a",
								},
								{
									key: "chg",
									label: "Since previous snapshot",
									value: fmtPct(i.instrument.price_change_pct, 1, true),
								},
								{
									key: "held",
									label: "Held across the book",
									value: fmtUsd(i.instrument.held_usd),
								},
								{
									key: "holders",
									label: "Clients holding",
									value: i.instrument.holder_clients,
								},
							]}
						/>
						{i.underlying_reference ? (
							<p className="mt-4 text-ink-2">
								Underlying reference: <b>{i.underlying_reference}</b>
							</p>
						) : null}
						<section className="mt-10" aria-labelledby="price-h">
							<h2 id="price-h" className="mb-3 text-xl">
								Price path
							</h2>
							<LineTrend
								points={i.price_path.map((p) => ({
									date: p.snapshot_date,
									value: p.price,
								}))}
								ariaLabel="Price over the snapshots"
								yLabel={`Price (${i.instrument.currency})`}
							/>
						</section>
						<section className="mt-10" aria-labelledby="holders-h">
							<h2 id="holders-h" className="mb-3 text-xl">
								Holders
							</h2>
							{i.holders.length ? (
								<>
									<DataTable
										columns={columns}
										data={i.holders}
										initialSort={{ id: "value_usd", desc: true }}
										rowId={(h) => `${h.portfolio_id}`}
									/>
									<div className="mt-6">
										<BarList
											rows={perClient(i.holders)}
											ariaLabel="USD held per client"
											valueLabel="USD held"
										/>
									</div>
								</>
							) : (
								<EmptyNotice>Not held by any client.</EmptyNotice>
							)}
						</section>
						<section className="mt-10" aria-labelledby="outlook-h">
							<h2 id="outlook-h" className="mb-3 text-xl">
								Outlook
							</h2>
							{i.outlook ? (
								<div className="space-y-4">
									<p className="max-w-[900px]">{i.outlook.summary}</p>
									{i.outlook.view ? (
										<ViewCard title="Instrument view" view={i.outlook.view} />
									) : null}
									{i.outlook.market_context.length ? (
										<p className="text-ink-2">
											Market context:{" "}
											{i.outlook.market_context
												.map(
													(m) =>
														`${titleCase(m.segment)} ${m.direction} (${m.horizon})`,
												)
												.join(" · ")}
										</p>
									) : null}
									{i.outlook.relevant_events.length ? (
										<ul className="space-y-1">
											{i.outlook.relevant_events.map((e) => (
												<li key={e.event_id}>
													<span className="num text-ink-muted">
														{fmtDate(e.event_date)}
													</span>{" "}
													· {e.severity} · {e.description}
												</li>
											))}
										</ul>
									) : null}
									{i.outlook.evidence_ids.length ? (
										<p className="flex flex-wrap gap-x-3">
											<span className="eyebrow">Evidence</span>
											{i.outlook.evidence_ids.map((e) => (
												<IdLink key={e} id={e} />
											))}
										</p>
									) : null}
								</div>
							) : (
								<EmptyNotice>
									No outlook exists for this instrument.
								</EmptyNotice>
							)}
						</section>
					</div>
				)}
			</StateBoundary>
		</>
	);
}
