import { useState } from "react";
import type { Schemas } from "#/api/client";
import { useData } from "#/api/queries";
import {
	EmptyNotice,
	GapNotice,
	PlaceholderBanner,
	StateBoundary,
} from "#/components/StateBoundary";
import { fmtPct, fmtUsd } from "#/lib/format";
import { CaseRange, Explainer } from "./CaseRange";
import {
	breachTone,
	CASE_LABEL,
	CASE_ORDER,
	conditionalBanner,
	hasFigures,
	isComputed,
	type ScenarioResult,
} from "./scenarios";

type Catalogue = Schemas["ScenarioCatalogue"];
type ClientScenarios = Schemas["ClientScenarios"];

export { breachTone };

export function ConditionalBanner({
	horizonMonths,
	partial,
}: {
	horizonMonths: number;
	partial?: boolean;
}) {
	return (
		<div
			role="note"
			className="my-3 border border-rule bg-surface-sunk px-3 py-2 text-ink-2"
			data-testid="conditional-banner"
		>
			<b className="font-semibold text-navy-950">
				{conditionalBanner(horizonMonths)}
			</b>
			{partial ? (
				<span data-testid="partial-notice">
					{" "}
					This result is partial: see the gaps below.
				</span>
			) : null}
		</div>
	);
}

function Section({
	title,
	children,
}: {
	title: string;
	children: React.ReactNode;
}) {
	return (
		<section>
			<h3 className="mb-2 text-lg">{title}</h3>
			{children}
		</section>
	);
}

function CollateralList({
	result,
	tone,
}: {
	result: ScenarioResult;
	tone: string;
}) {
	const any = CASE_ORDER.some((c) => result.cases[c]?.collateral.length);
	if (!any)
		return <p className="text-ink-muted">No credit facility affected.</p>;
	return (
		<ul className="space-y-1">
			{CASE_ORDER.flatMap((c) =>
				(result.cases[c]?.collateral ?? []).map((e) => (
					<li key={`${c}-${e.facility}`}>
						<span className="text-ink-muted">{CASE_LABEL[c]} · </span>
						{e.facility}: LTV {fmtPct(e.ltv_before_pct)} to{" "}
						{fmtPct(e.ltv_after_pct)} against a {fmtPct(e.trigger_pct)} trigger
						{e.breaches ? (
							<b className={tone}>
								{" "}
								· crosses the trigger
								{e.shortfall_usd
									? `, shortfall ${fmtUsd(e.shortfall_usd)}`
									: ""}
							</b>
						) : null}
					</li>
				)),
			)}
		</ul>
	);
}

function BandList({ result, tone }: { result: ScenarioResult; tone: string }) {
	const any = CASE_ORDER.some((c) => result.cases[c]?.bands.length);
	if (!any)
		return <p className="text-ink-muted">No band is crossed in any case.</p>;
	return (
		<ul className="space-y-1">
			{CASE_ORDER.flatMap((c) =>
				(result.cases[c]?.bands ?? []).map((b) => (
					<li key={`${c}-${b.portfolio}-${b.asset_class}`}>
						<span className="text-ink-muted">{CASE_LABEL[c]} · </span>
						{b.portfolio} · {b.asset_class}: {fmtPct(b.before_pct)} to{" "}
						{fmtPct(b.after_pct)} (band {fmtPct(b.band_min_pct, 0)} to{" "}
						{fmtPct(b.band_max_pct, 0)})
						<b className={tone}>
							{" "}
							· crosses {b.crosses === "out" ? "out of" : "into"} the band
						</b>
					</li>
				)),
			)}
		</ul>
	);
}

function PositionTable({ result }: { result: ScenarioResult }) {
	return (
		<table className="data-table">
			<thead>
				<tr>
					<th>Position</th>
					<th>Asset class</th>
					<th>Weight</th>
					<th>Worst</th>
					<th>Likely</th>
					<th>Best</th>
					<th>Likely change (USD)</th>
					<th>Channels</th>
				</tr>
			</thead>
			<tbody>
				{result.positions.map((p) => (
					<tr key={`${p.portfolio_id}-${p.instrument_id}-${p.instrument}`}>
						<td>{p.instrument}</td>
						<td>{p.asset_class}</td>
						<td className="num">{fmtPct(p.weight_pct)}</td>
						{CASE_ORDER.map((c) => (
							<td key={c} className="num">
								{fmtPct(p.moves[c]?.move_pct, 1, true)}
							</td>
						))}
						<td className="num">{fmtUsd(p.moves.likely?.delta_usd, false)}</td>
						<td>
							{p.mapping === "untouched" ? (
								<span className="text-ink-muted" title={p.reason}>
									Untouched
								</span>
							) : (
								p.channels.map((c) => (
									<div key={c.channel} title={c.why}>
										{c.channel} {fmtPct(c.likely_pct, 1, true)}
										{c.agent_assigned ? (
											<span className="text-ink-muted"> · agent-assigned</span>
										) : null}
									</div>
								))
							)}
						</td>
					</tr>
				))}
			</tbody>
		</table>
	);
}

function MarketMoves({
	market,
}: {
	market: NonNullable<ScenarioResult["market"]>;
}) {
	return (
		<details className="border border-rule bg-surface px-3 py-2">
			<summary className="cursor-pointer text-lg">
				Market moves behind this scenario
			</summary>
			{market.summary ? (
				<p className="mt-2 text-ink-2">{market.summary}</p>
			) : null}
			<table className="data-table mt-3">
				<thead>
					<tr>
						<th>Channel</th>
						<th>Worst</th>
						<th>Likely</th>
						<th>Best</th>
						<th>Why</th>
					</tr>
				</thead>
				<tbody>
					{market.channels.map((c) => (
						<tr key={c.channel}>
							<td>{c.channel}</td>
							<td className="num">{fmtPct(c.worst, 1, true)}</td>
							<td className="num">{fmtPct(c.likely, 1, true)}</td>
							<td className="num">{fmtPct(c.best, 1, true)}</td>
							<td>
								{c.rationale}
								<div className="text-xs text-ink-muted">
									{c.anchored_event
										? `Anchored to ${c.anchored_event.event_date}: ${c.anchored_event.description}`
										: c.anchor_note}
								</div>
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</details>
	);
}

export function ScenarioResultView({ result }: { result: ScenarioResult }) {
	const placeholder = result.status === "placeholder";
	const tone = breachTone(placeholder);
	const figures = hasFigures(result);
	return (
		<div className="mt-6 space-y-8" data-testid="scenario-result">
			{placeholder && figures ? (
				<PlaceholderBanner note={result.note} />
			) : isComputed(result.status) ? (
				<ConditionalBanner
					horizonMonths={result.horizon_months}
					partial={result.status === "partial"}
				/>
			) : null}
			{!figures ? (
				<EmptyNotice>
					{result.note || "No figures for this scenario."}
				</EmptyNotice>
			) : (
				<>
					<div className="border-y border-rule py-5">
						<CaseRange cases={result.cases} explainers={result.explainers} />
						<div className="mt-5 flex flex-wrap gap-x-12 gap-y-4">
							<div>
								<div className="metric-value num">
									{fmtPct(result.reached_pct, 0)}
								</div>
								<div className="mt-2 text-xs text-ink-2">Wealth reached</div>
								<div className="text-xs text-ink-muted">
									{result.untouched_count} holdings untouched
								</div>
								<Explainer
									label="Explain wealth reached"
									text={result.explainers.reached}
								/>
							</div>
						</div>
					</div>
					{result.summary ? (
						<p className="max-w-prose text-lg" data-testid="scenario-summary">
							{result.summary}
						</p>
					) : null}
				</>
			)}
			<dl className="grid gap-4 md:grid-cols-2">
				<div>
					<dt className="eyebrow mb-1">Premise</dt>
					<dd>{result.premise}</dd>
				</div>
				<div>
					<dt className="eyebrow mb-1">Mirrors the event</dt>
					<dd>{result.mirrors}</dd>
				</div>
				<div>
					<dt className="eyebrow mb-1">Horizon</dt>
					<dd>{result.horizon_months} months</dd>
				</div>
				<div className="md:col-span-2">
					<dt className="eyebrow mb-1">Caveat</dt>
					<dd className="text-ink-2">{result.caveat}</dd>
				</div>
			</dl>
			{result.market ? (
				<>
					{result.market.summary ? (
						<p className="text-ink-2" data-testid="market-summary">
							<b>The market under this scenario:</b> {result.market.summary}
						</p>
					) : null}
					<MarketMoves market={result.market} />
				</>
			) : null}
			{figures ? (
				<>
					<Section title="Collateral effects">
						<CollateralList result={result} tone={tone} />
						<Explainer
							label="Explain collateral effects"
							text={result.explainers.collateral}
						/>
					</Section>
					<Section title="Mandate bands crossed">
						<BandList result={result} tone={tone} />
						<Explainer
							label="Explain mandate bands"
							text={result.explainers.bands}
						/>
					</Section>
					<Section title="Per position">
						<PositionTable result={result} />
					</Section>
				</>
			) : null}
			<GapNotice gaps={result.gaps} />
		</div>
	);
}

export function ScenarioComparison({ results }: { results: ScenarioResult[] }) {
	return (
		<div className="mt-6" data-testid="scenario-comparison">
			<table className="data-table">
				<thead>
					<tr>
						<th>Scenario</th>
						<th>Horizon</th>
						<th>Likely (%)</th>
						<th>Likely (USD)</th>
						<th>Worst (%)</th>
						<th>Worst (USD)</th>
					</tr>
				</thead>
				<tbody>
					{results.map((r) => {
						const figures = hasFigures(r);
						return (
							<tr key={r.scenario_id}>
								<td>{r.name}</td>
								<td>{r.horizon_months} months</td>
								{figures ? (
									<>
										<td className="num">
											{fmtPct(r.cases.likely?.delta_pct, 1, true)}
										</td>
										<td className="num">
											{fmtUsd(r.cases.likely?.delta_usd, false)}
										</td>
										<td className="num">
											{fmtPct(r.cases.worst?.delta_pct, 1, true)}
										</td>
										<td className="num">
											{fmtUsd(r.cases.worst?.delta_usd, false)}
										</td>
									</>
								) : (
									<td colSpan={4} className="text-ink-muted">
										Not computed
									</td>
								)}
							</tr>
						);
					})}
				</tbody>
			</table>
			<p className="mt-2 text-xs text-ink-muted">
				Cases are conditional on each scenario, not probabilities, and are not
				additive across scenarios.
			</p>
		</div>
	);
}

const COMPARE = "__compare__";

export function ScenarioTab({
	clientId,
	initialScenario,
}: {
	clientId: string;
	initialScenario?: string;
}) {
	const catalogue = useData<Catalogue>("/scenarios");
	const results = useData<ClientScenarios>(`/clients/${clientId}/scenarios`);
	const [picked, setPicked] = useState<string | null>(initialScenario ?? null);
	return (
		<div className="mt-8" data-testid="scenario-tab">
			<StateBoundary
				query={catalogue}
				label="Loading scenarios"
				hidePlaceholder
			>
				{(cat) => {
					const selected = picked ?? cat.scenarios[0]?.scenario_id ?? null;
					const tab = (id: string, name: string) => (
						<button
							key={id}
							type="button"
							role="tab"
							aria-selected={id === selected}
							onClick={() => setPicked(id)}
							className={`border px-3 py-1.5 text-sm ${id === selected ? "border-navy-950 bg-navy-950 text-canvas" : "border-rule bg-surface text-ink-2 hover:border-slate-blue"}`}
						>
							{name}
						</button>
					);
					return (
						<>
							<div
								className="flex flex-wrap items-center gap-3"
								role="tablist"
								aria-label="Scenario"
							>
								{cat.scenarios.map((s) => tab(s.scenario_id, s.name))}
								{tab(COMPARE, "Compare scenarios")}
							</div>
							<StateBoundary
								query={results}
								label="Loading the scenario result"
								hidePlaceholder
							>
								{(r) => {
									if (selected === COMPARE)
										return <ScenarioComparison results={r.scenarios} />;
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
