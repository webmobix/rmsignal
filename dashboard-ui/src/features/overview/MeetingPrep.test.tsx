import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Overview } from "#/api/queries";
import { MeetingPrep } from "./MeetingPrep";

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

const prep = {
	from_date: "2026-08-26",
	to_date: "2026-09-09",
	clients: [
		{
			client_id: "CL-0011",
			client_name: "Tan Boon Huat",
			items: [
				{
					kind: "kyc",
					title: "KYC review",
					due_date: "2026-08-01",
					status: "overdue",
					action_id: null,
				},
			],
			latest_note: null,
		},
	],
} as unknown as Overview["meeting_prep"];

describe("MeetingPrep", () => {
	it("marks an overdue KYC review and links the client", () => {
		render(<MeetingPrep prep={prep} />);
		expect(screen.getByText("Overdue")).toHaveClass("text-alert");
		expect(screen.getByRole("link", { name: "Tan Boon Huat" })).toHaveAttribute(
			"href",
			"#CL-0011",
		);
	});
});
