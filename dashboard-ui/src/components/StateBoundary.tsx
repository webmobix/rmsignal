import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ApiError } from "#/api/client";

interface Gap {
	kind: string;
	description: string;
	subject?: string | null;
}

export function GapNotice({ gaps }: { gaps: readonly Gap[] | undefined }) {
	if (!gaps?.length) return null;
	return (
		<ul
			className="my-3 border-l-2 border-caution bg-caution-sunk px-3 py-2 text-xs text-ink-2"
			data-testid="gaps"
		>
			{gaps.map((g) => (
				<li key={`${g.kind}-${g.subject ?? ""}-${g.description}`}>
					<b className="font-semibold text-caution">
						Data gap · {g.kind.replace(/_/g, " ")}:
					</b>{" "}
					{g.description}
				</li>
			))}
		</ul>
	);
}

export function PlaceholderBanner({ note }: { note?: string | null }) {
	return (
		<div
			role="note"
			className="my-3 border border-dashed border-slate-blue bg-surface-sunk px-3 py-2 text-xs text-ink-2"
			data-testid="placeholder-banner"
		>
			<b className="font-semibold text-navy-950">Illustrative, not computed.</b>{" "}
			{(
				note ??
				"This region shows placeholder content, not a calculation on the holdings."
			).replace(/^Illustrative, not computed:?\s*/i, "")}
		</div>
	);
}

export function EmptyNotice({ children }: { children?: ReactNode }) {
	return (
		<p className="border border-dashed border-rule px-4 py-6 text-center text-sm text-ink-muted">
			{children ?? "Nothing to show."}
		</p>
	);
}

export function LoadingBlock({ label = "Loading" }: { label?: string }) {
	return (
		<output className="block animate-pulse border border-hair bg-surface px-4 py-8 text-center text-xs text-ink-muted">
			{label}…
		</output>
	);
}

export function ErrorBlock({
	error,
	onRetry,
}: {
	error: unknown;
	onRetry?: () => void;
}) {
	const message =
		error instanceof ApiError ? error.detail : "Something went wrong.";
	return (
		<div
			role="alert"
			className="border border-alert bg-alert-sunk px-4 py-3 text-sm text-alert"
		>
			<p>
				<b>Could not load this section.</b> {message}
			</p>
			{onRetry ? (
				<button
					type="button"
					onClick={onRetry}
					className="mt-2 text-xs underline"
				>
					Retry
				</button>
			) : null}
		</div>
	);
}

/**
 * One place for loading, error, empty, gap and placeholder states of a region.
 * `children` receives the loaded data; gaps and placeholder status are read from it.
 */
export function StateBoundary<T extends object>({
	query,
	children,
	isEmpty,
	label,
	hidePlaceholder,
	hideGaps,
}: {
	query: Pick<
		UseQueryResult<T>,
		"data" | "error" | "isError" | "isPending" | "refetch"
	>;
	children: (data: T) => ReactNode;
	isEmpty?: (data: T) => boolean;
	label?: string;
	hidePlaceholder?: boolean;
	hideGaps?: boolean;
}) {
	if (query.isError)
		return <ErrorBlock error={query.error} onRetry={() => query.refetch()} />;
	if (query.isPending || !query.data) return <LoadingBlock label={label} />;
	const data = query.data;
	const meta = data as {
		gaps?: readonly Gap[];
		status?: string;
		note?: string;
	};
	return (
		<>
			{meta.status === "placeholder" && !hidePlaceholder ? (
				<PlaceholderBanner note={meta.note} />
			) : null}
			{hideGaps ? null : <GapNotice gaps={meta.gaps} />}
			{isEmpty?.(data) ? <EmptyNotice /> : children(data)}
		</>
	);
}
