import { useState } from "react";
import type { Schemas } from "#/api/client";
import { useData } from "#/api/queries";
import { PlaceholderBanner, StateBoundary } from "#/components/StateBoundary";
import { fmtPct, fmtUsd } from "#/lib/format";

type Catalogue = Schemas["ScenarioCatalogue"];
type ClientScenarios = Schemas["ClientScenarios"];
type Result = ClientScenarios["scenarios"][number];

function Stat({
	label,
	value,
	hint,
}: {
	label: string;
	value: React.ReactNode;
	hint?: React.ReactNode;
}) {
	return (
		<div>
			<div className="metric-value num">{value}</div>
			<div className="mt-2 text-xs text-ink-2">{label}</div>
			{hint ? <div className="text-[11px] text-ink-muted">{hint}</div> : null}
		</div>
	);
}

/** Breach cues are neutral for placeholder results so they never read as a real alert. */
export function breachTone(placeholder: boolean): string {
	return placeholder ? "text-ink-2" : "text-alert";
}

export function ScenarioResultView({ result }: { result: Result }) {
	const placeholder = result.status === "placeholder";
	const tone = breachTone(placeholder);
	return (
		<div className="mt-6 space-y-8" data-testid="scenario-result">
			{placeholder ? <PlaceholderBanner note={result.note} /> : null}
			<div className="flex flex-wrap gap-x-12 gap-y-4 border-y border-rule py-5">
				<Stat
					label="Change in portfolio value"
					value={fmtPct(result.delta_pct, 1, true)}
					hint={`${fmtUsd(result.delta_usd, false)} · ${fmtUsd(result.before_usd)} to ${fmtUsd(result.after_usd)}`}
				/>
				<Stat
					label="Wealth reached"
					value={fmtPct(result.reached_pct, 0)}
					hint={`${result.untouched_count} holdings untouched`}
				/>
			</div>
			<dl className="grid gap-4 text-[13.5px] md:grid-cols-2">
				<div>
					<dt className="eyebrow mb-1">Premise</dt>
					<dd>{result.premise}</dd>
				</div>
				<div>
					<dt className="eyebrow mb-1">Mirrors the event</dt>
					<dd>{result.mirrors}</dd>
				</div>
				<div className="md:col-span-2">
					<dt className="eyebrow mb-1">Caveat</dt>
					<dd className="text-ink-2">{result.caveat}</dd>
				</div>
			</dl>
			<section>
				<h3 className="mb-2 text-[18px]">Collateral effects</h3>
				{result.collateral.length ? (
					<ul className="space-y-1 text-[13px]">
						{result.collateral.map((c) => (
							<li key={c.facility}>
								{c.facility}: LTV {fmtPct(c.ltv_before_pct)} to{" "}
								{fmtPct(c.ltv_after_pct)} against a {fmtPct(c.trigger_pct)}{" "}
								trigger
								{c.breaches ? (
									<b className={tone}>
										{" "}
										· crosses the trigger
										{c.shortfall_usd
											? `, shortfall ${fmtUsd(c.shortfall_usd)}`
											: ""}
									</b>
								) : null}
							</li>
						))}
					</ul>
				) : (
					<p className="text-xs text-ink-muted">No credit facility affected.</p>
				)}
			</section>
			<section>
				<h3 className="mb-2 text-[18px]">Mandate bands crossed</h3>
				{result.bands.length ? (
					<ul className="space-y-1 text-[13px]">
						{result.bands.map((b) => (
							<li key={`${b.portfolio}-${b.asset_class}`}>
								{b.portfolio} · {b.asset_class}: {fmtPct(b.before_pct)} to{" "}
								{fmtPct(b.after_pct)} (band {fmtPct(b.band_min_pct, 0)} to{" "}
								{fmtPct(b.band_max_pct, 0)})
								{b.crosses ? (
									<b className={tone}>
										{" "}
										· crosses {b.crosses === "out" ? "out of" : "into"} the band
									</b>
								) : null}
							</li>
						))}
					</ul>
				) : (
					<p className="text-xs text-ink-muted">No band is crossed.</p>
				)}
			</section>
			<section>
				<h3 className="mb-2 text-[18px]">Per position</h3>
				<table className="data-table">
					<thead>
						<tr>
							<th>Position</th>
							<th>Asset class</th>
							<th>Weight</th>
							<th>Move</th>
							<th>Change (USD)</th>
							<th>Channels</th>
						</tr>
					</thead>
					<tbody>
						{result.positions.map((p) => (
							<tr key={p.instrument}>
								<td>{p.instrument}</td>
								<td>{p.asset_class}</td>
								<td className="num">{fmtPct(p.weight_pct)}</td>
								<td className="num">{fmtPct(p.move_pct, 1, true)}</td>
								<td className="num">{fmtUsd(p.delta_usd, false)}</td>
								<td className="text-xs">
									{p.channels.map((c) => (
										<div key={c.channel}>
											{c.channel} {fmtPct(c.pct, 1, true)}: {c.why}
										</div>
									))}
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</section>
		</div>
	);
}

export function ScenarioTab({ clientId }: { clientId: string }) {
	const catalogue = useData<Catalogue>("/scenarios");
	const results = useData<ClientScenarios>(`/clients/${clientId}/scenarios`);
	const [picked, setPicked] = useState<string | null>(null);
	return (
		<div className="mt-8" data-testid="scenario-tab">
			<StateBoundary
				query={catalogue}
				label="Loading scenarios"
				hidePlaceholder
			>
				{(cat) => {
					const selected = picked ?? cat.scenarios[0]?.scenario_id ?? null;
					return (
						<>
							<div
								className="flex flex-wrap items-center gap-3"
								role="tablist"
								aria-label="Scenario"
							>
								{cat.scenarios.map((s) => (
									<button
										key={s.scenario_id}
										type="button"
										role="tab"
										aria-selected={s.scenario_id === selected}
										onClick={() => setPicked(s.scenario_id)}
										className={`border px-3 py-1.5 text-[13px] ${s.scenario_id === selected ? "border-navy-950 bg-navy-950 text-canvas" : "border-rule bg-surface text-ink-2 hover:border-slate-blue"}`}
									>
										{s.name}
									</button>
								))}
							</div>
							<StateBoundary
								query={results}
								label="Loading the scenario result"
							>
								{(r) => {
									const result = r.scenarios.find(
										(s) => s.scenario_id === selected,
									);
									return result ? <ScenarioResultView result={result} /> : null;
								}}
							</StateBoundary>
						</>
					);
				}}
			</StateBoundary>
		</div>
	);
}
