import type { Schemas } from "#/api/client";
import { IdLink } from "#/components/IdLink";
import { EmptyNotice } from "#/components/StateBoundary";
import { fmtDate } from "#/lib/format";
import { ActionTable } from "../overview/ActionList";
import { VERDICT_LABEL } from "./status";

type Detail = Schemas["ClientDetail"];

export function ActionsNotes({ detail }: { detail: Detail }) {
	return (
		<div className="space-y-10" data-testid="actions-notes">
			<section aria-labelledby="ca-h" className="mt-8">
				<h2 id="ca-h" className="mb-3 text-xl">
					Actions
				</h2>
				{detail.actions.length ? (
					<ActionTable actions={detail.actions} hideClient />
				) : (
					<EmptyNotice>No actions were derived for this client.</EmptyNotice>
				)}
			</section>
			<section aria-labelledby="notes-h">
				<h2 id="notes-h" className="mb-1 text-xl">
					RM notes against the data
				</h2>
				<p className="mb-3 text-ink-muted">
					Each note is checked against the holdings and reports.
				</p>
				{detail.notes.length ? (
					<ul className="space-y-3">
						{detail.notes.map((n) => {
							const contradicted = n.verdict === "contradicted";
							return (
								<li
									key={n.note_id}
									className={`card p-4 ${contradicted ? "border-alert" : ""}`}
									data-testid={`note-${n.verdict}`}
								>
									<div className="flex flex-wrap items-center gap-3 text-xs">
										<span className="num text-ink-muted">
											{fmtDate(n.note_date)} · {n.channel}
										</span>
										<span
											className={`font-semibold ${contradicted ? "text-alert" : n.verdict === "consistent" ? "text-positive" : "text-caution"}`}
										>
											{VERDICT_LABEL[n.verdict ?? ""] ?? n.verdict}
										</span>
									</div>
									<p className="mt-2">{n.note}</p>
									<p className="mt-2 text-ink-2">{n.rationale}</p>
									{n.evidence_ids.length || n.finding_refs.length ? (
										<p className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
											<span className="eyebrow">Evidence</span>
											{n.finding_refs.map((r) => (
												<IdLink key={r} id={r} />
											))}
											{n.evidence_ids.map((e) => (
												<IdLink key={e} id={e} />
											))}
										</p>
									) : null}
								</li>
							);
						})}
					</ul>
				) : (
					<EmptyNotice>No RM notes.</EmptyNotice>
				)}
			</section>
		</div>
	);
}
