import { useNavigate, useSearch } from "@tanstack/react-router";
import { useState } from "react";
import type { Schemas } from "#/api/client";
import type { ApiAction, Overview } from "#/api/queries";
import { useData } from "#/api/queries";
import { Drawer } from "#/components/Drawer";
import { IdLink } from "#/components/IdLink";
import { StateBoundary } from "#/components/StateBoundary";
import { TierBadge } from "#/components/TierBadge";
import { fmtDate, titleCase } from "#/lib/format";

type Evidence = Schemas["EvidenceResponse"];

export function EvidenceBlock({
	id,
	defaultOpen = false,
}: {
	id: string;
	defaultOpen?: boolean;
}) {
	const [open, setOpen] = useState(defaultOpen);
	return (
		<div className="border border-hair bg-surface">
			<button
				type="button"
				aria-expanded={open}
				onClick={() => setOpen(!open)}
				className="flex w-full items-center justify-between px-3 py-2 text-left text-xs"
			>
				<span className="num font-medium text-navy-700">{id}</span>
				<span className="text-ink-muted">
					{open ? "Hide" : "Show"} tool result
				</span>
			</button>
			{open ? <EvidenceBody id={id} /> : null}
		</div>
	);
}

function EvidenceBody({ id }: { id: string }) {
	const query = useData<Evidence>(`/evidence/${id}`);
	return (
		<div className="border-t border-hair px-3 py-3">
			<StateBoundary query={query} label="Loading evidence">
				{(ev) => {
					const result = ev.result as {
						status?: string;
						reason?: string | null;
						effective_snapshot_date?: string | null;
						sources?: {
							dataset: string;
							key: string;
							snapshot_date: string | null;
						}[];
						data?: unknown;
					};
					return (
						<div className="space-y-3" data-testid="evidence-body">
							<p className="text-ink-2">
								Status <b>{result.status ?? "n/a"}</b>
								{result.effective_snapshot_date ? (
									<> · data as of {fmtDate(result.effective_snapshot_date)}</>
								) : null}
								{result.reason ? <> · {result.reason}</> : null}
							</p>
							{result.sources?.length ? (
								<p className="text-ink-muted">
									Sources:{" "}
									{[
										...new Set(
											result.sources.map((s) => `${s.dataset} ${s.key}`),
										),
									]
										.slice(0, 8)
										.join(", ")}
								</p>
							) : null}
							<pre className="max-h-72 overflow-auto bg-surface-sunk p-2 text-xs leading-snug">
								{JSON.stringify(result.data, null, 2)}
							</pre>
							{ev.cited_by.length ? (
								<div>
									<div className="eyebrow mb-1">Cited by</div>
									<ul className="space-y-1">
										{ev.cited_by.map((c) => (
											<li key={c.ref}>
												<IdLink id={c.ref} />{" "}
												<span className="text-ink-muted">· {c.text}</span>
											</li>
										))}
									</ul>
								</div>
							) : null}
						</div>
					);
				}}
			</StateBoundary>
		</div>
	);
}

function Field({
	label,
	children,
}: {
	label: string;
	children: React.ReactNode;
}) {
	return (
		<div>
			<div className="eyebrow mb-1">{label}</div>
			<div className="text-ink">{children}</div>
		</div>
	);
}

export function ActionContent({ action }: { action: ApiAction }) {
	const portfolios = [
		...new Set(
			action.refs
				.map((r) => r.portfolio_id)
				.filter((p): p is string => Boolean(p)),
		),
	];
	return (
		<div className="space-y-5" data-testid="action-drawer">
			<div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-ink-2">
				<TierBadge tier={action.importance} />
				<span>{titleCase(action.category)}</span>
				<span>Horizon: {titleCase(action.horizon)}</span>
				<span className="num">Due {fmtDate(action.due_date)}</span>
			</div>
			<Field label="What">{action.what}</Field>
			<Field label="Why">{action.why}</Field>
			<Field label="Go to">
				<span className="flex flex-wrap gap-x-4">
					<IdLink id={action.client_id}>{action.client_name}</IdLink>
					{portfolios.map((p) => (
						<IdLink key={p} id={p} />
					))}
				</span>
			</Field>
			<div>
				<div className="eyebrow mb-2">Findings and evidence</div>
				{action.refs.length ? (
					<ul className="space-y-4">
						{action.refs.map((ref) => (
							<li key={ref.ref}>
								<p>
									<IdLink id={ref.ref} />{" "}
									<span className="text-ink-2">· {ref.claim}</span>
								</p>
								<div className="mt-2 space-y-2">
									{ref.evidence_ids.map((id) => (
										<EvidenceBlock key={id} id={id} />
									))}
								</div>
							</li>
						))}
					</ul>
				) : (
					<p className="text-ink-muted">
						This action cites no findings (coverage placeholder).
					</p>
				)}
			</div>
		</div>
	);
}

/** Drawer driven by the root search params: ?action=, ?evidence= or ?finding=. */
export function EvidenceDrawer() {
	const search = useSearch({ strict: false }) as {
		action?: string;
		evidence?: string;
		finding?: string;
	};
	const navigate = useNavigate();
	const overview = useData<Overview>("/overview");
	const open = Boolean(search.action || search.evidence || search.finding);
	const close = () =>
		navigate({
			to: ".",
			search: (prev: Record<string, unknown>) => ({
				...prev,
				action: undefined,
				evidence: undefined,
				finding: undefined,
			}),
			resetScroll: false,
		});

	let title = "Evidence";
	let eyebrow = "Evidence";
	let body: React.ReactNode = null;
	if (search.action) {
		const action = overview.data?.actions.find(
			(a) => a.action_id === search.action,
		);
		eyebrow = `Action · ${search.action}`;
		title = action?.title ?? search.action;
		body = action ? (
			<ActionContent action={action} />
		) : overview.isPending ? (
			<p className="text-ink-muted">Loading…</p>
		) : (
			<p className="text-ink-muted">
				This action is not in the current overview.
			</p>
		);
	} else if (search.evidence) {
		eyebrow = "Evidence";
		title = search.evidence;
		body = <EvidenceBlock id={search.evidence} defaultOpen />;
	} else if (search.finding) {
		eyebrow = "Finding";
		title = search.finding;
		body = <FindingContent refId={search.finding} />;
	}
	return (
		<Drawer open={open} onClose={close} title={title} eyebrow={eyebrow}>
			{body}
		</Drawer>
	);
}

function FindingContent({ refId }: { refId: string }) {
	const clientId = refId.split("#")[0];
	const query = useData<Schemas["ClientDetail"]>(`/clients/${clientId}`);
	return (
		<StateBoundary query={query} hideGaps>
			{(detail) => {
				const finding = detail.findings.find((f) => f.ref === refId);
				if (!finding)
					return <p className="text-ink-muted">Finding not found.</p>;
				return (
					<div className="space-y-4">
						<p>{finding.claim}</p>
						<p className="text-ink-muted">
							Confidence {finding.confidence} ·{" "}
							<IdLink id={finding.client_id} />
							{finding.portfolio_id ? (
								<>
									{" "}
									· <IdLink id={finding.portfolio_id} />
								</>
							) : null}
						</p>
						<div className="space-y-2">
							{finding.evidence_ids.map((id) => (
								<EvidenceBlock key={id} id={id} />
							))}
						</div>
					</div>
				);
			}}
		</StateBoundary>
	);
}
