import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SummaryText } from "./SummaryText";

vi.mock("#/components/IdLink", () => ({
	IdLink: ({ id, children }: { id: string; children?: React.ReactNode }) => (
		<a href={`#${id}`}>{children ?? id}</a>
	),
}));

const names = { "CL-0001": "Tan Boon Huat" };

describe("SummaryText", () => {
	it("renders a client as a bold link and the action in italic", () => {
		const { container } = render(
			<SummaryText text="[[CL-0001]] _call before Friday_." names={names} />,
		);
		const link = screen.getByRole("link", { name: "Tan Boon Huat" });
		expect(link.parentElement?.tagName).toBe("STRONG");
		expect(link.getAttribute("href")).toBe("#CL-0001");
		expect(container.querySelector("em")?.textContent).toBe(
			"call before Friday",
		);
		expect(container.textContent).toBe("Tan Boon Huat call before Friday.");
	});

	it("shows an unknown client id as plain text", () => {
		const { container } = render(
			<SummaryText text="[[CL-0099]] _act_" names={names} />,
		);
		expect(screen.queryByRole("link")).toBeNull();
		expect(container.textContent).toBe("CL-0099 act");
	});

	it("leaves text without markup, and snake_case words, untouched", () => {
		const { container } = render(
			<SummaryText text="Review the data_quality gap." names={names} />,
		);
		expect(container.querySelector("em")).toBeNull();
		expect(container.textContent).toBe("Review the data_quality gap.");
	});
});
