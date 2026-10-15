import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { idKind } from "#/lib/ids";

/** Every identifier renders as a link to its view (or opens its evidence drawer). */
export function IdLink({ id, children }: { id: string; children?: ReactNode }) {
	const label = children ?? id;
	const kind = idKind(id);
	const cls = "num font-medium text-navy-700 hover:text-navy-950";
	if (kind === "client")
		return (
			<Link to="/clients/$clientId" params={{ clientId: id }} className={cls}>
				{label}
			</Link>
		);
	if (kind === "portfolio")
		return (
			<Link
				to="/portfolios/$portfolioId"
				params={{ portfolioId: id }}
				className={cls}
			>
				{label}
			</Link>
		);
	if (kind === "instrument")
		return (
			<Link
				to="/instruments/$instrumentId"
				params={{ instrumentId: id }}
				className={cls}
			>
				{label}
			</Link>
		);
	return (
		<Link
			to="."
			search={(prev) => ({
				...prev,
				action: undefined,
				evidence: kind === "evidence" ? id : undefined,
				finding: kind === "finding" ? id : undefined,
			})}
			className={cls}
		>
			{label}
		</Link>
	);
}

export function OpenActionLink({
	id,
	children,
}: {
	id: string;
	children?: ReactNode;
}) {
	return (
		<Link
			to="."
			search={(prev) => ({
				...prev,
				action: id,
				evidence: undefined,
				finding: undefined,
			})}
			className="text-left font-medium text-navy-950 hover:text-navy-700"
		>
			{children ?? id}
		</Link>
	);
}
