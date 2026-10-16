import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

export interface Metric {
	key: string;
	label: ReactNode;
	value: ReactNode;
	hint?: ReactNode;
	/** Makes the label a link to the Actions page, filtered to a tier. */
	actionsTier?: string;
}

export function MetricStrip({
	metrics,
	children,
}: {
	metrics: Metric[];
	children?: ReactNode;
}) {
	return (
		<div className="mt-5 flex flex-wrap items-stretch gap-x-[clamp(24px,4vw,54px)] gap-y-4 border-y border-t-navy-950 border-b-rule py-5">
			{metrics.map((m) => (
				<div key={m.key} data-testid={`metric-${m.key}`}>
					<div className="metric-value num">{m.value}</div>
					<div className="mt-2 whitespace-nowrap text-xs text-ink-2">
						{m.actionsTier ? (
							<Link
								to="/actions"
								search={{ tier: m.actionsTier }}
								className="text-ink-2 underline decoration-rule underline-offset-2 hover:text-navy-950"
							>
								{m.label}
							</Link>
						) : (
							m.label
						)}
					</div>
					{m.hint ? (
						<div className="text-[11px] text-ink-muted">{m.hint}</div>
					) : null}
				</div>
			))}
			{children}
		</div>
	);
}
