import type { ReactNode } from "react";
import type { Schemas } from "#/api/client";
import { titleCase } from "#/lib/format";
import { IdLink } from "./IdLink";

type Reason = Schemas["Reason"];
type ViewLike = {
	direction: string;
	horizon: string;
	confidence: string;
	rationale: string;
	drivers: Reason[];
	risks: Reason[];
	would_change_if: string;
	change: Schemas["Change"];
};

const DIRECTION: Record<string, { word: string; tone: string; glyph: string }> =
	{
		positive: { word: "Positive", tone: "text-positive", glyph: "▲" },
		neutral: { word: "Neutral", tone: "text-ink-2", glyph: "●" },
		negative: { word: "Negative", tone: "text-alert", glyph: "▼" },
	};

function Reasons({ title, items }: { title: string; items: Reason[] }) {
	if (!items.length) return null;
	return (
		<div className="mt-3">
			<div className="eyebrow mb-1">{title}</div>
			<ul className="space-y-2 text-[13px]">
				{items.map((r) => (
					<li key={r.claim}>
						{r.claim}
						{r.evidence_ids.length || r.event_refs.length ? (
							<span className="ml-2 inline-flex flex-wrap gap-x-2 text-xs">
								{r.evidence_ids.map((id) => (
									<IdLink key={id} id={id}>
										evidence
									</IdLink>
								))}
								{r.event_refs.map((e) => (
									<span key={e} className="num text-ink-muted">
										{e}
									</span>
								))}
							</span>
						) : null}
					</li>
				))}
			</ul>
		</div>
	);
}

/** One market or instrument view: direction, horizon, confidence, rationale, drivers, risks, trigger. */
export function ViewCard({
	title,
	view,
}: {
	title: ReactNode;
	view: ViewLike;
}) {
	const d = DIRECTION[view.direction] ?? DIRECTION.neutral;
	return (
		<article className="card p-4" data-testid="view-card">
			<div className="flex flex-wrap items-baseline justify-between gap-2">
				<h3 className="text-[18px]">{title}</h3>
				<span className={`text-xs font-semibold ${d?.tone}`}>
					<span aria-hidden="true">{d?.glyph}</span> {d?.word} · {view.horizon}{" "}
					· {view.confidence} confidence
				</span>
			</div>
			<p className="mt-2 text-[13.5px]">{view.rationale}</p>
			<Reasons title="Drivers" items={view.drivers} />
			<Reasons title="Risks" items={view.risks} />
			<p className="mt-3 text-xs text-ink-2">
				<b>Would change if:</b> {view.would_change_if}
			</p>
			<p className="mt-2 text-xs text-ink-muted">
				{titleCase(view.change.kind)}
				{view.change.previous_direction
					? ` (was ${view.change.previous_direction})`
					: ""}
				: {view.change.why}
			</p>
		</article>
	);
}
