import { useState } from "react";
import type { Schemas } from "#/api/client";
import { useData } from "#/api/queries";
import { IdLink } from "#/components/IdLink";
import { EmptyNotice, StateBoundary } from "#/components/StateBoundary";
import { fmtDate, fmtPct, fmtUsd, titleCase } from "#/lib/format";

type Changes = Schemas["SnapshotChanges"];

function Select({
	label,
	value,
	options,
	onChange,
}: {
	label: string;
	value: string;
	options: string[];
	onChange: (v: string) => void;
}) {
	return (
		<label className="flex items-center gap-2 text-sm">
			<span className="eyebrow">{label}</span>
			<select
				value={value}
				onChange={(e) => onChange(e.target.value)}
				className="border border-rule bg-surface px-2 py-1 text-sm"
			>
				{options.map((o) => (
					<option key={o} value={o}>
						{fmtDate(o)}
					</option>
				))}
			</select>
		</label>
	);
}

export function SnapshotCompare({
	clientId,
	dates,
}: {
	clientId: string;
	dates: string[];
}) {
	const [from, setFrom] = useState(dates[0] ?? "");
	const [to, setTo] = useState(dates[dates.length - 1] ?? "");
	const query = useData<Changes>(`/clients/${clientId}/snapshot-changes`, {
		from,
		to,
	});
	if (dates.length < 2)
		return <EmptyNotice>Fewer than two snapshots are available.</EmptyNotice>;
	return (
		<div className="mt-8" data-testid="snapshot-compare">
			<div className="flex flex-wrap gap-6">
				<Select label="From" value={from} options={dates} onChange={setFrom} />
				<Select label="To" value={to} options={dates} onChange={setTo} />
			</div>
			<StateBoundary query={query} label="Comparing snapshots">
				{(d) => (
					<div className="mt-6 space-y-8">
						<p>
							Total <b className="num">{fmtUsd(d.total_from_usd)}</b> to{" "}
							<b className="num">{fmtUsd(d.total_to_usd)}</b> (
							{fmtPct(d.change_pct, 1, true)}, {fmtUsd(d.change_usd)}).
						</p>
						{d.portfolios.map((p) => (
							<section key={p.portfolio_id}>
								<h3 className="text-lg">
									<IdLink id={p.portfolio_id}>{p.portfolio_name}</IdLink>
								</h3>
								<p className="mt-1 text-ink-2">
									AuM {fmtUsd(p.aum_usd_from)} to {fmtUsd(p.aum_usd_to)} (
									{fmtPct(p.change_pct, 1, true)}). Unrealised P&amp;L change{" "}
									<span className="num">
										{fmtUsd(p.pnl_change_base, false)}
									</span>{" "}
									({p.base_currency}).
								</p>
								{p.positions.length ? (
									<table className="data-table mt-2">
										<thead>
											<tr>
												<th>Change</th>
												<th>Instrument</th>
												<th>Value from</th>
												<th>Value to</th>
												<th>Change (USD)</th>
											</tr>
										</thead>
										<tbody>
											{p.positions.map((pos) => (
												<tr key={`${pos.portfolio_id}-${pos.instrument_id}`}>
													<td>{titleCase(pos.change)}</td>
													<td>
														<IdLink id={pos.instrument_id}>
															{pos.instrument_name}
														</IdLink>
													</td>
													<td className="num">
														{pos.value_usd_from == null
															? "n/a"
															: fmtUsd(pos.value_usd_from)}
													</td>
													<td className="num">
														{pos.value_usd_to == null
															? "n/a"
															: fmtUsd(pos.value_usd_to)}
													</td>
													<td className="num">{fmtUsd(pos.change_usd)}</td>
												</tr>
											))}
										</tbody>
									</table>
								) : (
									<p className="mt-2 text-ink-muted">
										No positions added, removed or resized.
									</p>
								)}
							</section>
						))}
						<section>
							<h3 className="mb-2 text-lg">Events between the dates</h3>
							{d.events.length ? (
								<ul className="space-y-2">
									{d.events.map((e) => (
										<li key={`${e.event_date}-${e.description.slice(0, 20)}`}>
											<span className="num text-ink-muted">
												{fmtDate(e.event_date)}
											</span>{" "}
											· <b>{e.event_type}</b> ({e.severity}) · {e.description}
										</li>
									))}
								</ul>
							) : (
								<p className="text-ink-muted">No events between these dates.</p>
							)}
						</section>
					</div>
				)}
			</StateBoundary>
		</div>
	);
}
