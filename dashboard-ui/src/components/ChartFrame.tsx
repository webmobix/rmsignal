import type { ChartDefinition } from "@tanstack/charts/react";
import { Chart } from "@tanstack/charts/react/tooltip";
import { type ReactNode, useEffect, useState } from "react";

/**
 * The only place the charting library is mounted. Charts render client-only
 * (SSR support is untested for this app); the page around them still renders
 * on the server. Pass a memoised `definition`.
 */
export function ChartFrame<TDatum = unknown>({
	definition,
	ariaLabel,
	height = 320,
	initialWidth = 720,
	onSelect,
	tooltipBody,
	caption,
}: {
	// biome-ignore lint/suspicious/noExplicitAny: library generics are inferred at the call site
	definition: ChartDefinition<any, any, any>;
	ariaLabel: string;
	height?: number;
	initialWidth?: number;
	onSelect?: (datum: TDatum | null) => void;
	tooltipBody?: (datum: TDatum) => ReactNode;
	caption?: ReactNode;
}) {
	const [mounted, setMounted] = useState(false);
	useEffect(() => setMounted(true), []);
	return (
		<figure className="m-0" data-testid="chart-frame">
			<div style={{ minHeight: height }}>
				{mounted ? (
					<Chart
						definition={definition}
						ariaLabel={ariaLabel}
						height={height}
						initialWidth={initialWidth}
						renderTooltipBody={
							tooltipBody
								? (ctx) =>
										ctx.points[0]
											? tooltipBody(ctx.points[0].datum as TDatum)
											: ctx.defaultBody
								: undefined
						}
						onSelect={
							onSelect
								? (point) => onSelect(point ? (point.datum as TDatum) : null)
								: undefined
						}
					/>
				) : (
					<div
						className="grid h-full place-items-center text-xs text-ink-muted"
						style={{ height }}
					>
						Loading chart…
					</div>
				)}
			</div>
			{caption ? (
				<figcaption className="mt-2 text-ink-muted">{caption}</figcaption>
			) : null}
		</figure>
	);
}
