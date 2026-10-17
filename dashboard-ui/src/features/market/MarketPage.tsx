import type { Schemas } from "#/api/client";
import { type Overview, useData } from "#/api/queries";
import { IdLink } from "#/components/IdLink";
import { PageHeader } from "#/components/PageHeader";
import { EmptyNotice, StateBoundary } from "#/components/StateBoundary";
import { ViewCard } from "#/components/ViewCard";
import { fmtDate, fmtUsd, titleCase } from "#/lib/format";
import { ScenarioPanel } from "../scenarios/ScenarioPanel";

type Outlook = Schemas["MarketOutlookResponse"];
type Events = Schemas["EventsResponse"];
type EventRow = Events["events"][number];

const SEVERITY_TONE: Record<string, string> = {
	Severe: "text-alert",
	High: "text-caution",
	Medium: "text-ink-2",
	Low: "text-ink-muted",
};

export function EventItem({ event }: { event: EventRow }) {
	const r = event.reach;
	return (
		<li
			className="relative border-l border-rule pb-6 pl-5"
			data-testid="event-item"
		>
			<span
				className="absolute -left-[5px] top-1.5 size-[9px] rounded-full bg-navy-700"
				aria-hidden="true"
			/>
			<div className="flex flex-wrap items-baseline gap-x-3 text-xs">
				<span className="num text-ink-muted">{fmtDate(event.event_date)}</span>
				<span
					className={`font-semibold ${SEVERITY_TONE[event.severity] ?? ""}`}
				>
					{event.severity}
				</span>
				<span className="text-ink-muted">
					{event.event_type} · {event.region}
				</span>
			</div>
			<p className="mt-1">{event.description}</p>
			<p className="mt-1 text-ink-2">
				<b>Channels:</b> {event.primary_transmission}
			</p>
			<details className="mt-2">
				<summary className="cursor-pointer font-semibold text-navy-700">
					Reaches {r.clients.length} client{r.clients.length === 1 ? "" : "s"}{" "}
					and {r.instruments.length} instrument
					{r.instruments.length === 1 ? "" : "s"}{" "}
					<span className="font-normal text-ink-muted">(derived)</span>
				</summary>
				<div className="mt-2 space-y-2">
					<p className="text-ink-muted">
						Derived from the channel text, not reported by the source. Matched:{" "}
						{r.matched_channels.join(", ") || "none"}
						{r.unmatched_channels.length
							? `. Not matched: ${r.unmatched_channels.join(", ")}`
							: ""}
						.
					</p>
					{r.clients.length ? (
						<p className="flex flex-wrap gap-x-4 gap-y-1">
							<span className="eyebrow">Clients</span>
							{r.clients.map((c) => (
								<span key={c.client_id}>
									<IdLink id={c.client_id}>{c.client_name}</IdLink>{" "}
									<span className="num text-ink-muted">
										{fmtUsd(c.held_usd)}
									</span>
								</span>
							))}
						</p>
					) : null}
					{r.instruments.length ? (
						<p className="flex flex-wrap gap-x-4 gap-y-1">
							<span className="eyebrow">Instruments</span>
							{r.instruments.map((i) => (
								<span key={i.instrument_id}>
									<IdLink id={i.instrument_id}>{i.instrument_name}</IdLink>{" "}
									<span className="num text-ink-muted">
										{fmtUsd(i.held_usd)}
									</span>
								</span>
							))}
						</p>
					) : null}
				</div>
			</details>
		</li>
	);
}

export function MarketPage() {
	const outlook = useData<Outlook>("/market-outlook");
	const events = useData<Events>("/events");
	const overview = useData<Overview>("/overview");
	const names = Object.fromEntries(
		(overview.data?.client_rows ?? []).map((c) => [c.client_id, c.client_name]),
	);
	return (
		<>
			<PageHeader
				eyebrow="Market"
				title="Market views and what is moving them"
			/>
			<StateBoundary query={outlook} label="Loading the market outlook">
				{({ outlook: o }) =>
					o ? (
						<div data-testid="market-outlook">
							<p className="max-w-[900px] text-ink-2">{o.summary}</p>
							<p className="mt-2 text-ink-muted">
								Status {titleCase(o.status)} · as of {fmtDate(o.as_of)}
								{o.previous_as_of
									? ` · previous outlook ${fmtDate(o.previous_as_of)}`
									: " · first outlook"}
							</p>
							<section className="mt-8" aria-labelledby="views-h">
								<h2 id="views-h" className="mb-3 text-2xl">
									Views
								</h2>
								<div className="grid gap-4 lg:grid-cols-2">
									{o.views.map((v) => (
										<ViewCard
											key={v.segment}
											title={titleCase(v.segment)}
											view={v}
										/>
									))}
								</div>
							</section>
							<section className="mt-10" aria-labelledby="chg-h">
								<h2 id="chg-h" className="mb-2 text-xl">
									What changed
								</h2>
								<p className="max-w-[900px]">{o.changes_summary}</p>
							</section>
							<section className="mt-10" aria-labelledby="un-h">
								<h2 id="un-h" className="mb-2 text-xl">
									Events not yet addressed
								</h2>
								{o.unaddressed_events.length ? (
									<ul className="space-y-1">
										{o.unaddressed_events.map((e) => (
											<li key={e.event_id}>
												<span className="num text-ink-muted">
													{fmtDate(e.event_date)}
												</span>{" "}
												· {e.severity} · {e.description}
											</li>
										))}
									</ul>
								) : (
									<p className="text-ink-muted">
										All events are addressed by the views.
									</p>
								)}
							</section>
							{o.evidence_ids.length ? (
								<p className="mt-6 flex flex-wrap gap-x-3">
									<span className="eyebrow">Evidence</span>
									{o.evidence_ids.map((e) => (
										<IdLink key={e} id={e} />
									))}
								</p>
							) : null}
						</div>
					) : (
						<EmptyNotice>
							No market outlook is available for this date.
						</EmptyNotice>
					)
				}
			</StateBoundary>
			<ScenarioPanel names={names} />
			<section className="mt-12" aria-labelledby="tl-h">
				<h2 id="tl-h" className="mb-4 text-2xl">
					Event timeline
				</h2>
				<StateBoundary query={events} label="Loading events">
					{(e) =>
						e.events.length ? (
							<ol className="ml-1" data-testid="timeline">
								{[...e.events]
									.sort((a, b) => b.event_date.localeCompare(a.event_date))
									.map((ev) => (
										<EventItem
											key={`${ev.event_date}-${ev.description.slice(0, 24)}`}
											event={ev}
										/>
									))}
							</ol>
						) : (
							<EmptyNotice>No events recorded.</EmptyNotice>
						)
					}
				</StateBoundary>
			</section>
		</>
	);
}
