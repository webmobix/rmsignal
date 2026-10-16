export const MANDATE_LABEL: Record<string, string> = {
	in_band: "Within mandate",
	out_of_band: "Out of band",
	no_mandate: "No mandate",
};

export const VERDICT_LABEL: Record<string, string> = {
	consistent: "Consistent",
	contradicted: "Contradicted",
	unverifiable: "Unverifiable",
};

type BreachRecon = {
	status: "no_note" | "acknowledged" | "client_directed" | "contradicted";
	note_ids: string[];
	waiver_claimed?: boolean;
};

const WORST_FIRST = [
	"contradicted",
	"client_directed",
	"acknowledged",
] as const;

/** Short label of a breach's reconciliation status, with the notes behind it; null for `no_note`. */
export function breachLabel(b: BreachRecon): string | null {
	if (b.status === "no_note") return null;
	const ids = b.note_ids.length ? ` (${b.note_ids.join(", ")})` : "";
	if (b.status === "client_directed")
		return `${b.waiver_claimed ? "waiver claimed" : "client instruction"}${ids}`;
	return `${b.status === "contradicted" ? "contradicted" : "acknowledged"}${ids}`;
}

/** The most consequential reconciliation label of a portfolio's breaches, with the note ids of that status. */
export function worstBreachLabel(
	breaches: BreachRecon[] | undefined,
): string | null {
	for (const status of WORST_FIRST) {
		const hits = breaches?.filter((b) => b.status === status) ?? [];
		if (!hits.length) continue;
		const ids = [...new Set(hits.flatMap((b) => b.note_ids))];
		return breachLabel({
			status,
			note_ids: ids,
			waiver_claimed: hits.some((b) => b.waiver_claimed),
		});
	}
	return null;
}
