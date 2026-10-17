import type { ReactNode } from "react";
import { IdLink } from "#/components/IdLink";

const TOKEN = /\[\[([^[\]]+)\]\]|(?<![\w])_([^_]+)_(?![\w])/g;

/** The model summary: `[[CL-0001]]` is a client (bold link), `_text_` the action to take (italic); the rest is plain text. */
export function SummaryText({
	text,
	names,
}: {
	text: string;
	names: Record<string, string>;
}) {
	const out: ReactNode[] = [];
	let last = 0;
	for (const m of text.matchAll(TOKEN)) {
		if (m.index > last) out.push(text.slice(last, m.index));
		const id = m[1]?.trim();
		if (id !== undefined) {
			const name = names[id];
			out.push(
				name ? (
					<strong key={m.index}>
						<IdLink id={id}>{name}</IdLink>
					</strong>
				) : (
					id
				),
			);
		} else {
			out.push(<em key={m.index}>{m[2]}</em>);
		}
		last = m.index + m[0].length;
	}
	if (last < text.length) out.push(text.slice(last));
	return <>{out}</>;
}
