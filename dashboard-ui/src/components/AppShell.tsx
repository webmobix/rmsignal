import type { ReactNode } from "react";
import { TopBar } from "./TopBar";

export function AppShell({
	children,
	overlay,
}: {
	children: ReactNode;
	overlay?: ReactNode;
}) {
	return (
		<>
			<TopBar />
			<main className="mx-auto max-w-page px-gutter pb-16">{children}</main>
			{overlay}
		</>
	);
}
