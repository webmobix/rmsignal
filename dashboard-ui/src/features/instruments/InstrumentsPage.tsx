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
import { PageHeader } from "#/components/PageHeader";
import { StateBoundary } from "#/components/StateBoundary";
import { fmtPct, fmtUsd } from "#/lib/format";

type Row = Schemas["InstrumentRow"];
const helper = createColumnHelper<typeof tableFeaturesConfig, Row>();

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
	helper.accessor("sector", { header: "Sector" }),
	helper.accessor("region", { header: "Region" }),
	helper.accessor("latest_price", {
		header: "Latest price",
		cell: ({ row }) => (
			<span className="num">
				{row.original.latest_price == null
					? "n/a"
					: row.original.latest_price.toLocaleString("en-US", {
							maximumFractionDigits: 2,
						})}{" "}
				<span className="text-ink-muted">{row.original.currency}</span>
			</span>
		),
	}),
	helper.accessor("price_change_pct", {
		header: "Since previous",
		cell: ({ row }) => {
			const v = row.original.price_change_pct;
			return (
				<span className={`num ${v != null && v < 0 ? "text-alert" : ""}`}>
					{v == null ? "n/a" : fmtPct(v, 1, true)}
				</span>
			);
		},
	}),
	helper.accessor("held_usd", {
		header: "Held across book",
		cell: ({ row }) => (
			<span className="num">{fmtUsd(row.original.held_usd)}</span>
		),
	}),
	helper.accessor("has_outlook", {
		header: "Outlook",
		cell: ({ row }) => (row.original.has_outlook ? "Yes" : "None"),
	}),
]);

export function filterHeld(rows: Row[], heldOnly: boolean): Row[] {
	return rows.filter((r) => !heldOnly || (r.held_usd ?? 0) > 0);
}

export function byAssetClass(
	rows: Row[],
): { key: string; label: string; value: number }[] {
	const totals = new Map<string, number>();
	for (const r of rows)
		totals.set(
			r.asset_class,
			(totals.get(r.asset_class) ?? 0) + (r.held_usd ?? 0),
		);
	return [...totals.entries()]
		.filter(([, v]) => v > 0)
		.sort((a, b) => b[1] - a[1])
		.map(([k, v]) => ({ key: k, label: k, value: v }));
}

export function InstrumentsPage() {
	const query = useData<Row[]>("/instruments");
	const [heldOnly, setHeldOnly] = useState(false);
	const rows = useMemo(
		() => filterHeld(query.data ?? [], heldOnly),
		[query.data, heldOnly],
	);
	return (
		<>
			<PageHeader eyebrow="Instruments" title="Every instrument in the book" />
			<StateBoundary query={query} label="Loading instruments">
				{() => (
					<>
						<label className="mb-4 flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								checked={heldOnly}
								onChange={(e) => setHeldOnly(e.target.checked)}
							/>
							Held only
							<span className="num text-ink-muted">({rows.length} shown)</span>
						</label>
						<DataTable
							columns={columns}
							data={rows}
							initialSort={{ id: "held_usd", desc: true }}
							rowId={(r) => r.instrument_id}
						/>
						<section className="mt-10" aria-labelledby="ac-h">
							<h2 id="ac-h" className="mb-3 text-2xl">
								USD held by asset class
							</h2>
							<BarList
								rows={byAssetClass(query.data ?? [])}
								ariaLabel="USD held by asset class"
								valueLabel="USD held"
							/>
						</section>
					</>
				)}
			</StateBoundary>
		</>
	);
}
