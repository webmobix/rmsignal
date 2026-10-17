import { Link } from "@tanstack/react-router";
import { useState } from "react";
import type { Schemas } from "#/api/client";
import { useData } from "#/api/queries";
import {
	EmptyNotice,
	GapNotice,
	StateBoundary,
} from "#/components/StateBoundary";
import { fmtPct, fmtUsd } from "#/lib/format";
import { SummaryText } from "../overview/SummaryText";
import { CaseRange } from "./CaseRange";
import { ConditionalBanner } from "./ScenarioTab";
import { CASE_LABEL, hasFigures } from "./scenarios";

type Catalogue = Schemas["ScenarioCatalogue"];
type Rollup = Schemas["ScenarioRollup"];
type Line = Rollup["most_hit"][number];

const TOP = 5;

export function ClientLink({
	clientId,
	scenarioId,
	names,
}: {
	clientId: string;
	scenarioId: string;
	names: Record<string, string>;
}) {
	return (
		<Link
			to="/clients/$clientId"
			params={{ clientId }}
			search={{ tab: "scenarios", scenario: scenarioId }}
			className="font-medium text-navy-700 hover:text-navy-950"
		>
			{names[clientId] ?? clientId}
		</Link>
	);
}

function Ranking({
	title,
	lines,
	scenarioId,
	names,
	focus,
	testId,
}: {
	title: string;
	lines: Line[];
	scenarioId: string;
	names: Record<string, string>;
	focus: "worst" | "likely";
	testId: string;
}) {
	const [all, setAll] = useState(false);
	const shown = all ? lines : lines.slice(0, TOP);
	if (!lines.length) return null;
	return (
		<section data-testid={testId}>
			<h3 className="mb-2 text-lg">{title}</h3>
			<table className="data-table">
				<thead>
					<tr>
						<th>Client</th>
						<th>{CASE_LABEL[focus]} (%)</th>
						<th>{CASE_LABEL[focus]} (USD)</th>
					</tr>
				</thead>
				<tbody>
					{shown.map((l) => (
						<tr key={l.client_id}>
							<td>
								<ClientLink
									clientId={l.client_id}
									scenarioId={scenarioId}
									names={names}
								/>
							</td>
							<td className="num">
								{fmtPct(l.cases[focus]?.delta_pct, 1, true)}
							</td>
							<td className="num">
								{fmtUsd(l.cases[focus]?.delta_usd, false)}
							</td>
						</tr>
					))}
				</tbody>
			</table>
			{lines.length > TOP ? (
				<button
					type="button"
					onClick={() => setAll(!all)}
					className="mt-2 text-sm text-navy-700 underline decoration-rule underline-offset-2"
				>
					{all ? `Show the first ${TOP}` : `Show all ${lines.length} clients`}
				</button>
			) : null}
		</section>
	);
}

export function RollupView({
	rollup,
	names,
}: {
	rollup: Rollup;
	names: Record<string, string>;
}) {
	if (!hasFigures(rollup))
		return (
			<EmptyNotice>
				Scenarios have not been run for this date.
				{rollup.status === "insufficient_data" && rollup.note
					? ` ${rollup.note}`
					: ""}
			</EmptyNotice>
		);
	const cov = rollup.coverage;
	const partial = cov.computed < cov.total;
	return (
		<div className="mt-4 space-y-8" data-testid="scenario-rollup">
			<ConditionalBanner
				horizonMonths={rollup.horizon_months}
				partial={rollup.status === "partial"}
			/>
			<p className="text-sm text-ink-2" data-testid="coverage">
				<b>
					{cov.computed} of {cov.total} clients covered.
				</b>
				{partial
					? ` Not in these totals: ${cov.missing.map((c) => names[c] ?? c).join(", ")}.`
					: ""}
			</p>
			<div className="border-y border-rule py-5">
				<CaseRange cases={rollup.cases} />
			</div>
			{rollup.summary ? (
				<p className="max-w-prose text-lg" data-testid="rollup-summary">
					<SummaryText text={rollup.summary} names={names} />
				</p>
			) : null}
			<Ranking
				title="Most affected clients"
				lines={rollup.most_hit}
				scenarioId={rollup.scenario_id}
				names={names}
				focus="worst"
				testId="most-hit"
			/>
			<Ranking
				title="Clients who gain in the likely case"
				lines={rollup.beneficiaries}
				scenarioId={rollup.scenario_id}
				names={names}
				focus="likely"
				testId="beneficiaries"
			/>
			{rollup.crossings.length ? (
				<section data-testid="crossings">
					<h3 className="mb-2 text-lg">
						Mandate bands and facility triggers crossed
					</h3>
					<ul className="space-y-1">
						{rollup.crossings.map((x) => (
							<li
								key={`${x.client_id}-${x.case}-${x.kind}-${x.label}-${x.portfolio_id}`}
							>
								<span className="text-ink-muted">{CASE_LABEL[x.case]} · </span>
								<ClientLink
									clientId={x.client_id}
									scenarioId={rollup.scenario_id}
									names={names}
								/>
								: <span className="text-caution">{x.detail}</span>
							</li>
						))}
					</ul>
				</section>
			) : null}
			<GapNotice gaps={rollup.gaps} />
		</div>
	);
}

function Picked({
	scenarioId,
	names,
}: {
	scenarioId: string;
	names: Record<string, string>;
}) {
	const query = useData<Rollup>(`/scenarios/${scenarioId}/rollup`);
	return (
		<StateBoundary
			query={query}
			label="Loading the scenario roll-up"
			hidePlaceholder
			hideGaps
		>
			{(r) => <RollupView rollup={r} names={names} />}
		</StateBoundary>
	);
}

/** The RM's book under one scenario: totals for the three cases, the clients most affected, crossings and coverage. */
export function ScenarioPanel({ names }: { names: Record<string, string> }) {
	const catalogue = useData<Catalogue>("/scenarios");
	const [picked, setPicked] = useState<string | null>(null);
	return (
		<section
			aria-labelledby="scenario-h"
			className="mt-10"
			data-testid="scenario-panel"
		>
			<h2 id="scenario-h" className="mb-3 text-2xl">
				Scenarios
			</h2>
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
										className={`border px-3 py-1.5 text-sm ${s.scenario_id === selected ? "border-navy-950 bg-navy-950 text-canvas" : "border-rule bg-surface text-ink-2 hover:border-slate-blue"}`}
									>
										{s.name}
									</button>
								))}
							</div>
							{selected ? <Picked scenarioId={selected} names={names} /> : null}
						</>
					);
				}}
			</StateBoundary>
		</section>
	);
}
