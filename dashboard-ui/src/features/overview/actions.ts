import type { ApiAction } from "#/api/queries";

export const DATA_QUALITY = "data_quality";

/** Tiers urgent enough for the home page (when also horizon "immediate"). */
export const URGENT_TIERS: readonly string[] = ["critical", "high"];
export const URGENT_HORIZON = "immediate";

export interface ActionFilter {
	tier: string | null;
	category: string | null;
	horizon?: string | null;
}

/** Actions the home page lists: critical/high and immediate, never data quality. */
export function urgentActions(actions: ApiAction[]): ApiAction[] {
	return actions.filter(
		(a) =>
			a.category !== DATA_QUALITY &&
			URGENT_TIERS.includes(a.importance) &&
			a.horizon === URGENT_HORIZON,
	);
}

export interface SplitActions {
	risks: ApiAction[];
	dataQuality: ApiAction[];
}

/**
 * Tier filters both lanes; the category and horizon filters only narrow client risks.
 * Data-quality actions always sit in their own lane so they cannot crowd risks out.
 */
export function splitActions(
	actions: ApiAction[],
	filter: ActionFilter,
): SplitActions {
	const byTier = (a: ApiAction) => !filter.tier || a.importance === filter.tier;
	return {
		risks: actions.filter(
			(a) =>
				a.category !== DATA_QUALITY &&
				byTier(a) &&
				(!filter.category || a.category === filter.category) &&
				(!filter.horizon || a.horizon === filter.horizon),
		),
		dataQuality: actions.filter(
			(a) => a.category === DATA_QUALITY && byTier(a),
		),
	};
}

export function tierCounts(actions: ApiAction[]): Record<string, number> {
	const counts: Record<string, number> = {};
	for (const a of actions)
		counts[a.importance] = (counts[a.importance] ?? 0) + 1;
	return counts;
}
