import type { ReactNode } from "react";

export interface TabDef {
	id: string;
	label: ReactNode;
}

export function Tabs({
	tabs,
	value,
	onChange,
}: {
	tabs: TabDef[];
	value: string;
	onChange: (id: string) => void;
}) {
	return (
		<div role="tablist" className="flex flex-wrap gap-6 border-b border-rule">
			{tabs.map((tab) => {
				const on = tab.id === value;
				return (
					<button
						key={tab.id}
						type="button"
						role="tab"
						aria-selected={on}
						onClick={() => onChange(tab.id)}
						className={`-mb-px border-b-2 pb-2 pt-1 text-[13px] ${
							on
								? "border-navy-950 font-semibold text-navy-950"
								: "border-transparent text-ink-2 hover:text-navy-950"
						}`}
					>
						{tab.label}
					</button>
				);
			})}
		</div>
	);
}
