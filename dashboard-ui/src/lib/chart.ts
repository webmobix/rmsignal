import { scaleLog } from "d3-scale";

/** Colours as theme variables so charts follow the tokens. */
export const CHART_COLORS = [
	"var(--color-navy-700)",
	"var(--color-caution)",
	"var(--color-positive)",
	"var(--color-slate-blue)",
	"var(--color-alert)",
	"var(--color-navy-950)",
] as const;

/** Log scale for AuM, which spans roughly USD 8m to 88m. */
export function aumScale(min = 5e6, max = 1.2e8) {
	return scaleLog().domain([min, max]);
}
