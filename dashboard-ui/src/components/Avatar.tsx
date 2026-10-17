import { initials } from "#/lib/format";

/** Mocked identity: initials on a navy disc. There is no sign-in. */
export function Avatar({ name }: { name: string }) {
	return (
		<span
			aria-hidden="true"
			className="inline-flex size-8 items-center justify-center rounded-full bg-navy-950 text-xs font-semibold tracking-wide text-canvas"
		>
			{initials(name)}
		</span>
	);
}
