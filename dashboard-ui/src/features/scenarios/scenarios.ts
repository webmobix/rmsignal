import type { Schemas } from "#/api/client";

export type CaseImpact = Schemas["CaseImpact"];
export type Totals = Schemas["Totals"];
export type ScenarioResult = Schemas["ClientScenarios"]["scenarios"][number];
export type Status = ScenarioResult["status"];

/** Worst to best, so the range reads left to right. */
export const CASE_ORDER = ["worst", "likely", "best"] as const;
export type CaseName = (typeof CASE_ORDER)[number];

export const CASE_LABEL: Record<CaseName, string> = {
	worst: "Worst case",
	likely: "Likely case",
	best: "Best case",
};

export function hasFigures(r: { cases: Record<string, unknown> }): boolean {
	return CASE_ORDER.every((c) => r.cases[c] !== undefined);
}

export function isComputed(status: Status): boolean {
	return status === "computed" || status === "partial";
}

/** Breach cues are neutral for placeholder results and cautionary, never alarming, for computed ones: a scenario breach is a what-if. */
export function breachTone(placeholder: boolean): string {
	return placeholder ? "text-ink-2" : "text-caution";
}

/** Position of a value on a bar that always includes zero, as a percentage of the bar's width. */
export function barPosition(value: number, values: number[]): number {
	const lo = Math.min(0, ...values);
	const hi = Math.max(0, ...values);
	return hi === lo ? 50 : ((value - lo) / (hi - lo)) * 100;
}

export function conditionalBanner(horizonMonths: number): string {
	return `Conditional on this scenario, over ${horizonMonths} months. The likely case is a central case, not a probability; best and worst bracket it.`;
}
