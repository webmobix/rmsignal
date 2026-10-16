import { Link } from "@tanstack/react-router";
import type { Schemas } from "#/api/client";
import { IdLink } from "#/components/IdLink";
import { EmptyNotice } from "#/components/StateBoundary";
import { fmtDate, fmtPct, fmtUsd } from "#/lib/format";
import { BreachSection } from "./BreachSection";
import { SectorSection } from "./SectorSection";

type S = Schemas["CallSheet"];

const SEVERITY_TONE: Record<string, string> = {
	High: "text-alert",
	Medium: "text-caution",
};

function Tag({ children }: { children: React.ReactNode }) {
	return (
		<span className="ml-2 border border-rule px-1.5 py-px text-[11px] font-medium text-ink-muted">
			{children}
		</span>
	);
}

export function PerformanceCard({ s }: { s: S["performance"] }) {
	return (
		<div className="min-w-0 text-[13px]">
			<p>
				<span className="num text-[20px] font-semibold">
					{fmtUsd(s.aum_usd)}
				</span>{" "}
				<span className="num">
					{fmtPct(s.change_pct, 1, true)} ({fmtUsd(s.change_usd)})
				</span>{" "}
				<span className="text-ink-muted">
					since{" "}
					{s.previous_snapshot_date ? fmtDate(s.previous_snapshot_date) : "n/a"}
				</span>
			</p>
			<h3 className="mt-4 text-xs font-semibold uppercase text-ink-muted">
				Largest value changes
			</h3>
			{s.contributors.length ? (
				<ul className="mt-1 space-y-1" data-testid="contributors">
					{s.contributors.map((c) => (
						<li key={c.instrument_id}>
							<IdLink id={c.instrument_id} /> {c.instrument_name}{" "}
							<span
								className={`num ${c.change_usd < 0 ? "text-alert" : "text-positive"}`}
							>
								{c.change_usd > 0 ? "+" : ""}
								{fmtUsd(c.change_usd)}
							</span>
						</li>
					))}
				</ul>
			) : (
				<p className="text-ink-muted">No position changed in value.</p>
			)}
			{s.findings.length ? (
				<>
					<h3 className="mt-4 text-xs font-semibold uppercase text-ink-muted">
						What the analysis says
					</h3>
					<ul className="mt-1 space-y-1" data-testid="findings">
						{s.findings.map((f) => (
							<li key={f.ref}>
								{f.claim} <IdLink id={f.ref} />
							</li>
						))}
					</ul>
				</>
			) : null}
			{s.events.length ? (
				<>
					<h3 className="mt-4 text-xs font-semibold uppercase text-ink-muted">
						Events between the snapshots
					</h3>
					<ul className="mt-1 space-y-1">
						{s.events.map((e) => (
							<li key={e.event_id}>
								<span className="num text-ink-muted">
									{fmtDate(e.event_date)}
								</span>{" "}
								<Link to="/market" className="font-medium text-navy-700">
									{e.description}
								</Link>
							</li>
						))}
					</ul>
				</>
			) : null}
		</div>
	);
}

export function MandateCard({ s }: { s: S["mandate"] }) {
	if (!s.applicable)
		return <EmptyNotice>{s.statement || "No mandate applies."}</EmptyNotice>;
	return (
		<div className="min-w-0 text-[13px]">
			<p className="text-ink-2">{s.statement}</p>
			{s.bands.some((b) => b.out_of_band) ? (
				<ul
					className="mt-2 space-y-1 font-medium text-alert"
					data-testid="cs-bands"
				>
					{s.bands
						.filter((b) => b.out_of_band)
						.map((b) => (
							<li key={b.asset_class}>
								{b.asset_class}: weight {fmtPct(b.weight_pct)} against{" "}
								{b.breach === "above_max"
									? `a maximum of ${fmtPct(b.max_pct)}`
									: `a minimum of ${fmtPct(b.min_pct)}`}
							</li>
						))}
				</ul>
			) : (
				<p className="mt-2 text-positive">
					All asset classes are within their bands.
				</p>
			)}
			{s.position_limit.max_single_position_pct != null ? (
				<p className="mt-2 text-xs text-ink-2">
					Largest position{" "}
					<IdLink id={s.position_limit.largest_instrument_id ?? ""} /> at{" "}
					{fmtPct(s.position_limit.largest_weight_pct)} against a
					single-position limit of{" "}
					{fmtPct(s.position_limit.max_single_position_pct)}
					{s.position_limit.breaches.length ? (
						<b className="text-alert"> (breached)</b>
					) : null}
					.
				</p>
			) : null}
			<div>
				<BreachSection
					embedded
					exclusions={s.exclusion_breaches}
					reconciliation={s.breach_reconciliation}
				/>
			</div>
			{s.open_actions.length ? (
				<>
					<h3 className="mt-4 text-xs font-semibold uppercase text-ink-muted">
						Open actions
					</h3>
					<ul className="mt-1 space-y-1" data-testid="open-actions">
						{s.open_actions.map((a) => (
							<li key={a.action_id}>
								<Link
									to="/actions"
									search={{ action: a.action_id }}
									className="font-medium text-navy-700"
								>
									{a.title}
								</Link>{" "}
								<span className="text-ink-muted">
									{a.importance}
									{a.due_date ? ` · due ${fmtDate(a.due_date)}` : ""}
								</span>
							</li>
						))}
					</ul>
				</>
			) : null}
		</div>
	);
}

export function OwnershipCard({ s }: { s: S["ownership"] }) {
	return (
		<div className="min-w-0">
			<SectorSection exposure={s.sector_exposure} />
		</div>
	);
}

export function BankViewRow({
	e,
	asOf,
}: {
	e: S["bank_view"]["entries"][number];
	asOf: string;
}) {
	const o = e.outlook;
	return (
		<li
			className="min-w-0 border-b border-hair py-2"
			data-testid="bank-view-row"
		>
			<div>
				<IdLink id={e.instrument_id} /> {e.instrument_name}{" "}
				<span className="num text-ink-muted">{fmtPct(e.weight_pct)}</span>
			</div>
			{o ? (
				<div className="text-ink-2">
					<span className="font-medium">
						Bank view as of {fmtDate(o.as_of)}
					</span>
					: {o.view.direction}, {o.view.horizon} horizon, {o.view.confidence}{" "}
					confidence
					{o.older_than_as_of ? <Tag>older than {fmtDate(asOf)}</Tag> : null}
					{o.view.rationale ? <p className="mt-1">{o.view.rationale}</p> : null}
					{o.view.drivers.length ? (
						<ul className="mt-1 list-disc pl-5 text-xs">
							{o.view.drivers.map((d) => (
								<li key={d.claim}>{d.claim}</li>
							))}
						</ul>
					) : null}
					{o.market_context.length ? (
						<p className="mt-1 text-xs text-ink-muted">
							Market view as of {fmtDate(o.market_outlook_as_of)}:{" "}
							{o.market_context
								.map((m) => `${m.segment} ${m.direction}`)
								.join(", ")}
						</p>
					) : null}
				</div>
			) : (
				<div className="text-ink-muted">no outlook</div>
			)}
		</li>
	);
}

export function BankViewCard({ s, asOf }: { s: S["bank_view"]; asOf: string }) {
	if (!s.entries.length) return <EmptyNotice>No positions.</EmptyNotice>;
	return (
		<div className="min-w-0 text-[13px]">
			<p className="mb-2 text-xs text-ink-muted">
				The bank's own views, each as of its date. They are not advice.
			</p>
			<ul data-testid="bank-view">
				{s.entries.map((e) => (
					<BankViewRow key={e.instrument_id} e={e} asOf={asOf} />
				))}
			</ul>
		</div>
	);
}

export function EventsCard({ s }: { s: S["events"] }) {
	if (!s.events.length)
		return <EmptyNotice>No event matches the holdings.</EmptyNotice>;
	return (
		<ul className="min-w-0 space-y-3 text-[13px]" data-testid="cs-event-list">
			{s.events.map((e) => (
				<li key={e.event_id}>
					<span className="num text-ink-muted">{fmtDate(e.event_date)}</span>{" "}
					<b className={SEVERITY_TONE[e.severity] ?? ""}>{e.severity}</b>{" "}
					<Link to="/market" className="font-medium text-navy-700">
						{e.description}
					</Link>
					<div className="text-xs text-ink-muted">
						Concerns:{" "}
						{e.instruments.map((i, n) => (
							<span key={i.instrument_id}>
								{n ? ", " : ""}
								<IdLink id={i.instrument_id} /> (matched on{" "}
								{[...new Set(i.matched_on.map((m) => m.field))].join(", ")})
							</span>
						))}
					</div>
				</li>
			))}
		</ul>
	);
}

export function CashCard({ s }: { s: S["cash_credit"] }) {
	const liq = s.client_liquidity;
	return (
		<div className="min-w-0 text-[13px]">
			{s.facilities.length ? (
				<ul className="space-y-1" data-testid="cs-facilities">
					{s.facilities.map((f) => (
						<li key={f.facility_id}>
							{f.facility_type} {f.facility_id}: LTV{" "}
							{fmtPct(f.current?.ltv_pct)} against a margin-call trigger of{" "}
							{fmtPct(f.margin_call_ltv_pct)}
							{f.ltv_gap_pp != null
								? ` (${f.ltv_gap_pp.toFixed(1)}pp of room)`
								: ""}
							, headroom {fmtUsd(f.current?.headroom)}
						</li>
					))}
				</ul>
			) : (
				<p className="text-ink-muted">
					No credit facility is secured on this portfolio.
				</p>
			)}
			<h3 className="mt-4 text-xs font-semibold uppercase text-ink-muted">
				Liquidity and planned needs <Tag>client level</Tag>
			</h3>
			{liq ? (
				<>
					<p className="mt-1">
						Daily-liquid assets {fmtUsd(liq.daily_liquid_usd)} against needs of{" "}
						{fmtUsd(liq.needs_total_usd)} within {liq.horizon_days} days
						{liq.shortfall_usd > 0 ? (
							<b className="text-alert">
								{" "}
								(short by {fmtUsd(liq.shortfall_usd)})
							</b>
						) : null}
						.
					</p>
					<ul className="mt-1 space-y-1" data-testid="cs-needs">
						{liq.items.map((i) => (
							<li key={i.id}>
								{i.description} <Tag>client level</Tag>{" "}
								<span className="num text-ink-muted">
									{i.currency} {i.amount.toLocaleString("en-US")} ·{" "}
									{fmtDate(i.due_from)} to {fmtDate(i.due_to)} · {i.certainty}
								</span>
							</li>
						))}
					</ul>
				</>
			) : (
				<p className="text-ink-muted">No liquidity data.</p>
			)}
		</div>
	);
}

export function ConversationCard({
	s,
	clientId,
}: {
	s: S["conversation"];
	clientId: string;
}) {
	return (
		<div className="min-w-0 text-[13px]">
			<h3 className="text-xs font-semibold uppercase text-ink-muted">
				Latest notes <Tag>client level</Tag>
			</h3>
			{s.notes.length ? (
				<ul className="mt-1 space-y-3" data-testid="cs-notes">
					{s.notes.map((n) => (
						<li key={n.note_id}>
							<Link
								to="/clients/$clientId"
								params={{ clientId }}
								className="num font-medium text-navy-700"
							>
								{n.note_id}
							</Link>{" "}
							<span className="num text-ink-muted">
								{fmtDate(n.note_date)} · {n.channel}
							</span>
							<blockquote className="mt-1 border-l-2 border-rule pl-3 text-ink-2">
								“{n.note}”
							</blockquote>
						</li>
					))}
				</ul>
			) : (
				<p className="text-ink-muted">No notes up to this date.</p>
			)}
			{s.note_total > s.notes.length ? (
				<p className="mt-1 text-xs text-ink-muted">
					Showing the latest {s.notes.length} of {s.note_total} notes.
				</p>
			) : null}
			<h3 className="mt-4 text-xs font-semibold uppercase text-ink-muted">
				Open commitments <Tag>client level</Tag>
			</h3>
			{s.commitments.length ? (
				<ul className="mt-1 space-y-1">
					{s.commitments.map((c) => (
						<li key={c.commitment_id}>
							{c.fund_name}{" "}
							<span className="num text-ink-muted">
								uncalled {c.currency} {c.uncalled.toLocaleString("en-US")}
								{c.expected_call_window ? ` · ${c.expected_call_window}` : ""}
							</span>
						</li>
					))}
				</ul>
			) : (
				<p className="text-ink-muted">No open commitments.</p>
			)}
		</div>
	);
}
