export type IdKind =
	| "client"
	| "portfolio"
	| "instrument"
	| "evidence"
	| "finding";

/** Classify an identifier by its shape so IdLink can route it. */
export function idKind(id: string): IdKind {
	if (id.startsWith("ev_")) return "evidence";
	if (id.includes("#")) return "finding";
	if (/^CL-\d+$/.test(id)) return "client";
	if (/^PF-\d+$/.test(id)) return "portfolio";
	return "instrument";
}
