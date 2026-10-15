import type { ReactNode } from "react";
import { useAsOf } from "#/api/queries";
import { fmtDate } from "#/lib/format";

export function PageHeader({
	eyebrow,
	title,
	lede,
	actions,
}: {
	eyebrow?: string;
	title: ReactNode;
	lede?: ReactNode;
	actions?: ReactNode;
}) {
	const asOf = useAsOf();
	return (
		<header className="pt-8 pb-5">
			<div className="eyebrow mb-3 flex items-center gap-3">
				<span data-testid="masthead-date">{asOf ? fmtDate(asOf) : "…"}</span>
				{eyebrow ? <span>· {eyebrow}</span> : null}
			</div>
			<div className="flex flex-wrap items-end justify-between gap-4">
				<h1 className="max-w-[26ch] text-[clamp(28px,3.6vw,40px)] leading-[1.12]">
					{title}
				</h1>
				{actions}
			</div>
			{lede ? (
				<p className="mt-4 max-w-[900px] text-[16px] text-ink-2">{lede}</p>
			) : null}
		</header>
	);
}
