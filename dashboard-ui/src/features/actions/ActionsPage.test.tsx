import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Overview } from "#/api/queries";
import { ActionsView } from "./ActionsPage";

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
	category: string,
	horizon: string,
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

const overview = (actions: unknown[]) =>
	({
		actions,
		by_category: [
			{ category: "mandate_drift", count: 2 },
			{ category: "data_quality", count: 1 },
		],
	}) as unknown as Overview;

const all = overview([
	act("a", "low", "mandate_drift", "later"),
	act("b", "high", "mandate_drift", "immediate"),
	act("c", "medium", "data_quality", "later"),
]);

describe("ActionsView", () => {
	it("lists tier-filtered actions and the lane", () => {
		render(<ActionsView overview={all} tier="low" onTier={() => {}} />);
		const risks = screen.getByTestId("risk-actions");
		expect(within(risks).getByText("Title a")).toBeInTheDocument();
		expect(within(risks).queryByText("Title b")).toBeNull();
		expect(screen.getByTestId("dq-lane")).toBeInTheDocument();
	});
	it("filters by horizon", () => {
		render(<ActionsView overview={all} tier={null} onTier={() => {}} />);
		fireEvent.click(screen.getByRole("button", { name: "Immediate" }));
		const risks = screen.getByTestId("risk-actions");
		expect(within(risks).getByText("Title b")).toBeInTheDocument();
		expect(within(risks).queryByText("Title a")).toBeNull();
	});
	it("shows an empty lane notice", () => {
		render(
			<ActionsView
				overview={overview([act("a", "low", "mandate_drift", "later")])}
				tier={null}
				onTier={() => {}}
			/>,
		);
		expect(screen.getByText("No data-quality items.")).toBeInTheDocument();
	});
});
