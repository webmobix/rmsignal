import type { Overview } from "#/api/queries";
import { useData } from "#/api/queries";
import { MetricStrip } from "#/components/MetricStrip";
import { PageHeader } from "#/components/PageHeader";
import { StateBoundary } from "#/components/StateBoundary";
import { fmtUsd, titleCase } from "#/lib/format";
import { ActionsPanel } from "./ActionsPanel";
import { tierCounts } from "./actions";
import { ClientMatrix } from "./ClientMatrix";
import { MeetingPrep } from "./MeetingPrep";

export function OverviewPage() {
	const query = useData<Overview>("/overview");
	return (
		<>
			<PageHeader
				eyebrow="Overview"
				title="Who to call first, and why"
				lede={query.data?.summary}
			/>
			<StateBoundary query={query} label="Loading the overview">
				{(ov) => {
					const counts = tierCounts(ov.actions);
					return (
						<>
							<MetricStrip
								metrics={[
									{
										key: "clients",
										value: ov.clients.length,
										label: "Clients",
									},
									{
										key: "aum",
										value: fmtUsd(ov.total_aum_usd),
										label: "Assets under management",
									},
									{
										key: "actions",
										value: ov.actions.length,
										label: "Next actions",
									},
									...Object.entries(counts).map(([tier, n]) => ({
										key: `tier-${tier}`,
										value: n,
										label: titleCase(tier),
									})),
									{
										key: "status",
										value: titleCase(ov.status),
										label: "Analysis status",
									},
								]}
							/>
							{ov.themes.length ? (
								<ul
									className="mt-5 flex flex-wrap gap-2 text-xs"
									aria-label="Themes"
								>
									{ov.themes.map((t) => (
										<li
											key={t.title}
											className="border border-rule bg-surface px-2.5 py-1 text-ink-2"
										>
											{t.title}{" "}
											<span className="num text-ink-muted">
												{t.action_ids.length}
											</span>
										</li>
									))}
								</ul>
							) : null}
							<ActionsPanel overview={ov} />
							<section aria-labelledby="matrix-h" className="mt-10">
								<h2 id="matrix-h" className="mb-3 text-[26px]">
									Client matrix
								</h2>
								<ClientMatrix rows={ov.client_rows} />
							</section>
							<MeetingPrep prep={ov.meeting_prep} />
						</>
					);
				}}
			</StateBoundary>
		</>
	);
}
