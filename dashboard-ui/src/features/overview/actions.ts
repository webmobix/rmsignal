import type { ApiAction } from "#/api/queries";

export const DATA_QUALITY = "data_quality";

export interface ActionFilter {
	tier: string | null;
	category: string | null;
}

export interface SplitActions {
	risks: ApiAction[];
	dataQuality: ApiAction[];
}

/**
 * Tier filters both lanes; the category filter only narrows client risks.
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
				(!filter.category || a.category === filter.category),
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
