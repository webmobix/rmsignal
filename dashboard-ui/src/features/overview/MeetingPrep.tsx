import type { Overview } from "#/api/queries";
import { IdLink, OpenActionLink } from "#/components/IdLink";
import { EmptyNotice } from "#/components/StateBoundary";
import { fmtDate, titleCase } from "#/lib/format";

export function MeetingPrep({ prep }: { prep: Overview["meeting_prep"] }) {
	return (
		<section aria-labelledby="prep-h" className="mt-10">
			<h2 id="prep-h" className="text-2xl">
				Meeting prep
			</h2>
			<p className="mt-1 text-ink-muted">
				{fmtDate(prep.from_date)} to {fmtDate(prep.to_date)}: actions falling
				due, KYC reviews, and your latest note per client.
			</p>
			<div
				className="mt-4 grid gap-4 md:grid-cols-2"
				data-testid="meeting-prep"
			>
				{prep.clients.length === 0 ? (
					<EmptyNotice>Nothing falls due in this window.</EmptyNotice>
				) : null}
				{prep.clients.map((c) => (
					<article key={c.client_id} className="card p-4">
						<h3 className="text-lg">
							<IdLink id={c.client_id}>{c.client_name}</IdLink>
						</h3>
						<ul className="mt-2 space-y-1">
							{c.items.map((item) => (
								<li
									key={`${item.kind}-${item.action_id ?? item.title}`}
									className="flex flex-wrap gap-x-2"
								>
									<span className="eyebrow">
										{item.kind === "kyc" ? "KYC" : "Action"}
									</span>
									{item.action_id ? (
										<OpenActionLink id={item.action_id}>
											{item.title}
										</OpenActionLink>
									) : (
										<span>{item.title}</span>
									)}
									<span className="num text-ink-muted">
										due {fmtDate(item.due_date)}
									</span>
									<span
										className={
											item.status === "overdue"
												? "font-semibold text-alert"
												: "text-ink-muted"
										}
									>
										{item.status === "overdue"
											? "Overdue"
											: titleCase(item.status)}
									</span>
								</li>
							))}
						</ul>
						{c.latest_note ? (
							<blockquote className="mt-3 border-l-2 border-rule pl-3 text-ink-2">
								<span className="num text-ink-muted">
									{fmtDate(c.latest_note.note_date)} · {c.latest_note.channel}
								</span>
								<p className="mt-1 line-clamp-3">{c.latest_note.note}</p>
							</blockquote>
						) : null}
					</article>
				))}
			</div>
		</section>
	);
}
