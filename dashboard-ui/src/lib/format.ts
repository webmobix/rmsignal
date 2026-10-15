const usd = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function fmtUsd(
	value: number | null | undefined,
	compact = true,
): string {
	if (value === null || value === undefined) return "n/a";
	const abs = Math.abs(value);
	if (compact && abs >= 1e9) return `USD ${(value / 1e9).toFixed(2)}bn`;
	if (compact && abs >= 1e6) return `USD ${(value / 1e6).toFixed(1)}m`;
	return `USD ${usd.format(value)}`;
}

export function fmtPct(
	value: number | null | undefined,
	digits = 1,
	signed = false,
): string {
	if (value === null || value === undefined) return "n/a";
	const sign = signed && value > 0 ? "+" : "";
	return `${sign}${value.toFixed(digits)}%`;
}

const MONTHS = [
	"Jan",
	"Feb",
	"Mar",
	"Apr",
	"May",
	"Jun",
	"Jul",
	"Aug",
	"Sep",
	"Oct",
	"Nov",
	"Dec",
];

/** ISO date -> "26 Aug 2026" (UTC so server and browser agree). */
export function fmtDate(iso: string | null | undefined): string {
	if (!iso) return "n/a";
	const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
	if (!y || !m || !d) return iso;
	return `${d} ${MONTHS[m - 1]} ${y}`;
}

export function initials(name: string): string {
	return name
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((part) => part[0]?.toUpperCase())
		.join("");
}

export function titleCase(value: string): string {
	return value.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

const compactFmt = new Intl.NumberFormat("en-US", {
	notation: "compact",
	maximumFractionDigits: 1,
});

/** Axis tick label: 46.7M, 1.2B. */
export function fmtCompact(value: number): string {
	return compactFmt.format(value);
}
