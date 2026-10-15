import { TanStackDevtools } from "@tanstack/react-devtools";
import type { QueryClient } from "@tanstack/react-query";
import {
	createRootRouteWithContext,
	HeadContent,
	Outlet,
	Scripts,
} from "@tanstack/react-router";
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools";
import { AppShell } from "../components/AppShell";
import { EvidenceDrawer } from "../features/overview/EvidenceDrawer";
import TanStackQueryDevtools from "../integrations/tanstack-query/devtools";
import appCss from "../styles.css?url";

export interface RootSearch {
	action?: string;
	evidence?: string;
	finding?: string;
}

interface MyRouterContext {
	queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<MyRouterContext>()({
	component: () => (
		<AppShell overlay={<EvidenceDrawer />}>
			<Outlet />
		</AppShell>
	),
	validateSearch: (search: Record<string, unknown>): RootSearch => ({
		action: typeof search.action === "string" ? search.action : undefined,
		evidence: typeof search.evidence === "string" ? search.evidence : undefined,
		finding: typeof search.finding === "string" ? search.finding : undefined,
	}),
	notFoundComponent: () => (
		<AppShell>
			<p className="py-16 text-ink-2">This page does not exist.</p>
		</AppShell>
	),
	head: () => ({
		meta: [
			{
				charSet: "utf-8",
			},
			{
				name: "viewport",
				content: "width=device-width, initial-scale=1",
			},
			{
				title: "RMSignal · Global WM Bank",
			},
		],
		links: [
			{
				rel: "stylesheet",
				href: appCss,
			},
		],
	}),
	shellComponent: RootDocument,
});

function RootDocument({ children }: { children: React.ReactNode }) {
	return (
		<html lang="en">
			<head>
				<HeadContent />
			</head>
			<body>
				{children}
				<TanStackDevtools
					config={{
						position: "bottom-right",
					}}
					plugins={[
						{
							name: "Tanstack Router",
							render: <TanStackRouterDevtoolsPanel />,
						},
						TanStackQueryDevtools,
					]}
				/>
				<Scripts />
			</body>
		</html>
	);
}
