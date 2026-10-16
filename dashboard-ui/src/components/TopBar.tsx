import { Link } from "@tanstack/react-router";
import { useRm } from "#/api/queries";
import { Avatar } from "./Avatar";

const NAV = [
	{ to: "/", label: "Overview" },
	{ to: "/actions", label: "Actions" },
	{ to: "/clients", label: "Clients" },
	{ to: "/instruments", label: "Instruments" },
	{ to: "/market", label: "Market" },
] as const;

export function TopBar() {
	const rm = useRm();
	return (
		<div className="border-b border-rule bg-surface">
			<div className="mx-auto flex max-w-page flex-wrap items-center gap-x-6 gap-y-2 px-gutter py-3">
				<Link
					to="/"
					className="flex items-center gap-3 font-serif text-[17px] text-navy-950 no-underline"
				>
					<span className="font-semibold tracking-tight">Global WM Bank</span>
					<span aria-hidden="true" className="h-5 w-px bg-rule" />
					<span>RMSignal</span>
				</Link>
				<nav aria-label="Primary" className="flex gap-5 text-[13px]">
					{NAV.map((item) => (
						<Link
							key={item.to}
							to={item.to}
							activeOptions={{ exact: item.to === "/" }}
							className="py-1 text-ink-2 no-underline hover:text-navy-950"
							activeProps={{
								className:
									"py-1 font-semibold text-navy-950 no-underline border-b border-navy-950",
							}}
						>
							{item.label}
						</Link>
					))}
				</nav>
				<div
					className="ml-auto flex items-center gap-3 text-[12.5px]"
					data-testid="rm-identity"
				>
					{rm.data ? (
						<>
							<div className="text-right leading-tight">
								<div className="font-semibold text-navy-950">
									{rm.data.rm_name}
								</div>
								<div className="text-ink-muted">Relationship Manager</div>
							</div>
							<Avatar name={rm.data.rm_name} />
						</>
					) : null}
				</div>
			</div>
		</div>
	);
}
