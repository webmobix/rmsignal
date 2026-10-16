import { Link } from "@tanstack/react-router";
import type { Overview } from "#/api/queries";
import { TIER_COLOR, TIER_LABEL, TIERS } from "#/lib/tiers";
import { ActionTable } from "./ActionList";
import { urgentActions } from "./actions";

export function TierFilter({
	counts,
	value,
	onChange,
}: {
	counts: Record<string, number>;
	value: string | null;
	onChange: (tier: string | null) => void;
}) {
	return (
		<fieldset
			className="m-0 flex min-w-0 flex-wrap items-center gap-x-5 gap-y-2 border-0 p-0"
			aria-label="Filter by importance"
		>
			{TIERS.filter((t) => counts[t]).map((tier) => {
				const on = value === tier;
				const dim = value !== null && !on;
				return (
					<button
						key={tier}
						type="button"
						aria-pressed={on}
						onClick={() => onChange(on ? null : tier)}
						className={`flex items-center gap-2 text-[13px] ${dim ? "opacity-50" : ""} ${on ? "font-semibold text-navy-950 shadow-[inset_0_-1px_0_0_var(--color-navy-950)]" : "text-ink-2"}`}
					>
						<span
							className="size-2 rounded-full"
							style={{ background: TIER_COLOR[tier] }}
						/>
						<span className="num font-serif text-[22px] leading-none text-navy-950">
							{counts[tier]}
						</span>
						{TIER_LABEL[tier]}
					</button>
				);
			})}
		</fieldset>
	);
}

export function ActionsPanel({ overview }: { overview: Overview }) {
	const urgent = urgentActions(overview.actions);
	const more = overview.actions.length - urgent.length;
	return (
		<section aria-labelledby="actions-h" className="mt-10">
			<h2 id="actions-h" className="text-[26px]">
				Needs action now
			</h2>
			<p className="mt-1 text-xs text-ink-muted">
				Critical and high importance, immediate horizon.
			</p>
			<div className="mt-4" data-testid="risk-actions">
				<ActionTable actions={urgent} empty="Nothing needs immediate action." />
			</div>
			<p className="mt-3 text-[13px]">
				<Link
					to="/actions"
					className="font-medium text-navy-950 hover:text-navy-700"
				>
					{more} more {more === 1 ? "action" : "actions"}
				</Link>{" "}
				<span className="text-ink-muted">
					including medium and low importance, and data quality
				</span>
			</p>
		</section>
	);
}
