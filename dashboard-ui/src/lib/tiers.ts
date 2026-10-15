export const TIERS = ["critical", "high", "medium", "low"] as const;
export type Tier = (typeof TIERS)[number];

export const TIER_LABEL: Record<string, string> = {
	critical: "Critical",
	high: "High",
	medium: "Medium",
	low: "Low",
	none: "No action",
};

/** Theme-token colour per tier (CSS variables, so charts and badges agree). */
export const TIER_COLOR: Record<string, string> = {
	critical: "var(--color-alert)",
	high: "var(--color-caution)",
	medium: "var(--color-navy-700)",
	low: "var(--color-slate-blue)",
	none: "var(--color-muted-blue)",
};

/** Non-colour cue so tiers stay legible without colour: glyph per tier. */
export const TIER_GLYPH: Record<string, string> = {
	critical: "▲▲",
	high: "▲",
	medium: "●",
	low: "○",
	none: "–",
};
