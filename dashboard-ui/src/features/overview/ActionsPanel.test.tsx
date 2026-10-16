import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Overview } from "#/api/queries";
import { ActionsPanel } from "./ActionsPanel";

vi.mock("@tanstack/react-router", () => ({
	Link: ({ to, children }: { to: string; children?: React.ReactNode }) => (
		<a href={to}>{children}</a>
	),
}));
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

const act = (
	id: string,
	importance: string,
	horizon: string,
	category = "x",
) => ({
	action_id: id,
	title: `Title ${id}`,
	client_id: "CL-1",
	client_name: "Client",
	rank: 1,
	importance,
	category,
	horizon,
	due_date: null,
});
const ov = (actions: unknown[]) => ({ actions }) as unknown as Overview;

describe("ActionsPanel", () => {
	it("lists only urgent actions and links to the rest", () => {
		render(
			<ActionsPanel
				overview={ov([
					act("a", "critical", "immediate"),
					act("b", "high", "within_30_days"),
					act("c", "medium", "immediate"),
					act("d", "critical", "immediate", "data_quality"),
				])}
			/>,
		);
		const list = screen.getByTestId("risk-actions");
		expect(within(list).getByText("Title a")).toBeInTheDocument();
		expect(within(list).queryByText("Title b")).toBeNull();
		expect(within(list).queryByText("Title c")).toBeNull();
		expect(within(list).queryByText("Title d")).toBeNull();
		expect(
			screen.getByRole("link", { name: "3 more actions" }),
		).toHaveAttribute("href", "/actions");
		expect(screen.queryByTestId("dq-lane")).toBeNull();
	});
	it("shows an empty notice when nothing is urgent", () => {
		render(<ActionsPanel overview={ov([act("b", "low", "later")])} />);
		expect(
			screen.getByText("Nothing needs immediate action."),
		).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: "1 more action" }),
		).toBeInTheDocument();
	});
});
