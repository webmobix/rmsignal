import { useMemo } from "react";
import type { Schemas } from "#/api/client";
import { useData } from "#/api/queries";
import { BarList } from "#/components/charts/BarList";
import { StackedHistory } from "#/components/charts/StackedHistory";
import {
	createColumnHelper,
	DataTable,
	type tableFeaturesConfig,
} from "#/components/DataTable";
import { IdLink } from "#/components/IdLink";
import { MetricStrip } from "#/components/MetricStrip";
import { EmptyNotice, StateBoundary } from "#/components/StateBoundary";
import { fmtDate, fmtPct, fmtUsd, titleCase } from "#/lib/format";

type Detail = Schemas["ClientDetail"];
type Consolidated = Detail["consolidated"];
type History = Schemas["AumHistory"];
type Position = NonNullable<Consolidated["top_positions"]>[number];
type LookThrough = NonNullable<Consolidated["look_through"]>[number];

const posHelper = createColumnHelper<typeof tableFeaturesConfig, Position>();
const posColumns = posHelper.columns([
	posHelper.accessor("instrument_name", {
		header: "Position",
		cell: ({ row }) => (
			<div>
				<IdLink id={row.original.instrument_id}>
					{row.original.instrument_name}
				</IdLink>
				<div className="text-xs text-ink-muted">
					{row.original.portfolio_ids.join(", ")}
				</div>
			</div>
		),
	}),
	posHelper.accessor("asset_class", { header: "Asset class" }),
	posHelper.accessor("value_usd", {
		header: "Value",
		cell: ({ row }) => (
			<span className="num">{fmtUsd(row.original.value_usd)}</span>
		),
	}),
	posHelper.accessor("weight_pct", {
		header: "Weight",
		cell: ({ row }) => (
			<span className="num">{fmtPct(row.original.weight_pct)}</span>
		),
	}),
]);

const ltHelper = createColumnHelper<typeof tableFeaturesConfig, LookThrough>();
const ltColumns = ltHelper.columns([
	ltHelper.accessor("name", {
		header: "Underlying name",
		cell: ({ row }) => (
			<div>
				{row.original.name}
				{row.original.via_look_through ? (
					<span className="ml-2 text-xs text-ink-muted">via look-through</span>
				) : null}
			</div>
		),
	}),
	ltHelper.accessor("value_usd", {
		header: "Exposure",
		cell: ({ row }) => (
			<span className="num">{fmtUsd(row.original.value_usd)}</span>
		),
	}),
	ltHelper.accessor("share_pct", {
		header: "Share of client",
		cell: ({ row }) => (
			<span className="num">{fmtPct(row.original.share_pct)}</span>
		),
	}),
	ltHelper.accessor("instrument_ids", {
		header: "Instruments",
		cell: ({ row }) => (
			<span className="flex flex-wrap gap-x-2 text-xs">
				{row.original.instrument_ids.map((id) => (
					<IdLink key={id} id={id} />
				))}
			</span>
		),
	}),
]);

function Section({
	title,
	id,
	children,
}: {
	title: string;
	id: string;
	children: React.ReactNode;
}) {
	return (
		<section aria-labelledby={id} className="mt-10">
			<h2 id={id} className="mb-3 text-xl">
				{title}
			</h2>
			{children}
		</section>
	);
}

const toBars = (rows: { key: string; value_usd: number }[] | undefined) =>
	(rows ?? []).map((r) => ({ key: r.key, label: r.key, value: r.value_usd }));

export function ClientSummary({
	detail,
	children,
}: {
	detail: Detail;
	children?: React.ReactNode;
}) {
	const c = detail.consolidated;
	const history = useData<History>(
		`/clients/${detail.profile.client_id}/aum-history`,
	);
	const series = useMemo(
		() =>
			history.data?.portfolios.map((p) => ({
				id: p.portfolio_id,
				label: p.portfolio_name,
				points: p.points.map((q) => ({
					date: q.snapshot_date,
					value: q.aum_usd,
				})),
			})) ?? [],
		[history.data],
	);
	const eventDates = useMemo(
		() => history.data?.events.map((e) => e.event_date) ?? [],
		[history.data],
	);
	const liq = c.liquidity;
	return (
		<div data-testid="client-summary">
			<MetricStrip
				metrics={[
					{ key: "aum", label: "Total AuM", value: fmtUsd(c.total_aum_usd) },
					{
						key: "change",
						label: `Change since ${fmtDate(c.previous_snapshot_date)}`,
						value: fmtPct(c.change_pct, 1, true),
						hint: fmtUsd(c.change_usd),
					},
					{
						key: "portfolios",
						label: "Portfolios",
						value: detail.portfolios.length,
					},
					{
						key: "hhi",
						label: "Concentration (HHI)",
						value: c.hhi == null ? "n/a" : Math.round(c.hhi),
					},
				]}
			/>
			{children}
			<Section title="AuM history by portfolio" id="hist-h">
				<StateBoundary query={history} label="Loading history">
					{() => (
						<>
							<StackedHistory
								series={series}
								eventDates={eventDates}
								ariaLabel="Assets under management by portfolio over time"
							/>
							<p className="mt-2 text-ink-muted">
								Dashed lines mark events in the period:{" "}
								{history.data?.events
									.map((e) => `${fmtDate(e.event_date)} ${e.event_type}`)
									.join(" · ")}
							</p>
						</>
					)}
				</StateBoundary>
			</Section>
			<div className="grid gap-x-10 md:grid-cols-2">
				<Section title="Combined allocation" id="alloc-h">
					{c.allocation?.length ? (
						<BarList
							rows={toBars(c.allocation)}
							ariaLabel="Allocation by asset class"
							valueLabel="USD"
						/>
					) : (
						<EmptyNotice>No allocation data.</EmptyNotice>
					)}
				</Section>
				<Section title="Currency exposure" id="ccy-h">
					{c.currency_exposure?.length ? (
						<BarList
							rows={toBars(c.currency_exposure)}
							ariaLabel="Currency exposure"
							valueLabel="USD"
						/>
					) : (
						<EmptyNotice>No currency data.</EmptyNotice>
					)}
				</Section>
			</div>
			<Section title="Largest positions" id="pos-h">
				{c.top_positions?.length ? (
					<DataTable
						columns={posColumns}
						data={c.top_positions}
						rowId={(p) => p.instrument_id}
					/>
				) : (
					<EmptyNotice />
				)}
			</Section>
			<Section title="Look-through to underlying names" id="lt-h">
				{c.look_through?.length ? (
					<DataTable
						columns={ltColumns}
						data={c.look_through}
						initialSort={{ id: "share_pct", desc: true }}
						rowId={(p) => p.name}
					/>
				) : (
					<EmptyNotice />
				)}
			</Section>
			<Section title="Liquidity against planned needs" id="liq-h">
				{liq ? (
					<div className="space-y-3" data-testid="liquidity">
						<p>
							Next {liq.horizon_days} days (to {fmtDate(liq.horizon_end)}):
							daily-liquid assets{" "}
							<b className="num">{fmtUsd(liq.daily_liquid_usd)}</b> against
							needs of <b className="num">{fmtUsd(liq.needs_total_usd)}</b>
							{liq.coverage_ratio != null ? (
								<> ({liq.coverage_ratio.toFixed(1)}x cover)</>
							) : null}
							.{" "}
							{(liq.shortfall_usd ?? 0) > 0 ? (
								<b className="text-alert">
									Shortfall {fmtUsd(liq.shortfall_usd)}.
								</b>
							) : (
								<span className="text-positive">No shortfall.</span>
							)}
						</p>
						{liq.items.length ? (
							<ul className="space-y-1 text-ink-2">
								{liq.items.map((i) => (
									<li key={i.id}>
										<span className="eyebrow mr-2">{titleCase(i.kind)}</span>
										{i.description} ·{" "}
										<span className="num">{fmtUsd(i.usd)}</span> ·{" "}
										{fmtDate(i.due_from)} to {fmtDate(i.due_to)} · {i.certainty}
									</li>
								))}
							</ul>
						) : null}
					</div>
				) : (
					<EmptyNotice>No liquidity analysis available.</EmptyNotice>
				)}
			</Section>
			<Section title="Credit headroom" id="credit-h">
				{c.facilities?.length ? (
					<ul className="space-y-2" data-testid="credit">
						{c.facilities.map((f) => (
							<li key={f.facility_id} className="card p-3">
								<b>{f.facility_type}</b>{" "}
								<span className="num text-ink-muted">{f.facility_id}</span> on{" "}
								<IdLink id={f.portfolio_id} />: LTV{" "}
								<b className="num">{fmtPct(f.current?.ltv_pct)}</b> against a{" "}
								<span className="num">{fmtPct(f.margin_call_ltv_pct)}</span>{" "}
								margin-call trigger (
								<span
									className={
										f.ltv_gap_pp != null && f.ltv_gap_pp < 5
											? "font-semibold text-alert"
											: ""
									}
								>
									{f.ltv_gap_pp == null
										? "n/a"
										: `${f.ltv_gap_pp.toFixed(1)}pp`}{" "}
									headroom
								</span>
								). Drawn <span className="num">{fmtUsd(f.current?.drawn)}</span>{" "}
								of <span className="num">{fmtUsd(f.credit_limit)}</span>.
							</li>
						))}
					</ul>
				) : (
					<EmptyNotice>No credit facility.</EmptyNotice>
				)}
			</Section>
		</div>
	);
}
