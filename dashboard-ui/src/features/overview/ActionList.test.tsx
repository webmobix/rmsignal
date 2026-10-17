import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ApiAction } from "#/api/queries";
import { ActionTable } from "./ActionList";

vi.mock("#/components/IdLink", () => ({
	IdLink: ({ id, children }: { id: string; children?: React.ReactNode }) => (
		<a href={`#${id}`}>{children ?? id}</a>
	),
	OpenActionLink: ({
		id,
		children,
	}: {
		id: string;
		children?: React.ReactNode;
	}) => <a href={`#${id}`}>{children ?? id}</a>,
}));

const actions = [
	{
		action_id: "A-1",
		title: "Title A-1",
		client_id: "CL-1",
		client_name: "Client One",
		rank: 1,
		importance: "high",
		category: "x",
		horizon: "immediate",
		due_date: null,
	},
] as unknown as ApiAction[];

describe("ActionTable", () => {
	it("shows the Client column by default", () => {
		render(<ActionTable actions={actions} />);
		expect(
			screen.getByRole("columnheader", { name: /^Client/ }),
		).toBeInTheDocument();
		expect(screen.getByText("Client One")).toBeInTheDocument();
	});

	it("omits the Client column when hideClient is set", () => {
		render(<ActionTable actions={actions} hideClient />);
		expect(
			screen.queryByRole("columnheader", { name: /^Client/ }),
		).not.toBeInTheDocument();
		expect(screen.queryByText("Client One")).not.toBeInTheDocument();
		expect(
			screen.getByRole("columnheader", { name: /^Action/ }),
		).toBeInTheDocument();
	});
});
