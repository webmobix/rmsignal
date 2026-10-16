import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MetricStrip } from "./MetricStrip";

vi.mock("@tanstack/react-router", () => ({
	Link: ({
		to,
		search,
		children,
	}: {
		to: string;
		search: { tier: string };
		children?: React.ReactNode;
	}) => <a href={`${to}?tier=${search.tier}`}>{children}</a>,
}));

describe("MetricStrip", () => {
	it("links a tier metric to the filtered Actions page", () => {
		render(
			<MetricStrip
				metrics={[
					{
						key: "tier-medium",
						value: 5,
						label: "Medium",
						actionsTier: "medium",
					},
					{ key: "clients", value: 20, label: "Clients" },
				]}
			/>,
		);
		expect(screen.getByRole("link", { name: "Medium" })).toHaveAttribute(
			"href",
			"/actions?tier=medium",
		);
		expect(screen.queryByRole("link", { name: "Clients" })).toBeNull();
	});
});
