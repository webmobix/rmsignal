import { TIER_COLOR, TIER_GLYPH, TIER_LABEL } from "#/lib/tiers";

export function TierBadge({ tier }: { tier: string | null | undefined }) {
	const key = tier ?? "none";
	return (
		<span
			className="inline-flex items-center gap-1.5 text-xs font-semibold"
			style={{ color: TIER_COLOR[key] ?? TIER_COLOR.none }}
		>
			<span aria-hidden="true" className="text-xs leading-none">
				{TIER_GLYPH[key] ?? "–"}
			</span>
			{TIER_LABEL[key] ?? key}
		</span>
	);
}
