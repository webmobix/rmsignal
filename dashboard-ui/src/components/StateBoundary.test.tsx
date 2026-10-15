import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "#/api/client";
import { StateBoundary } from "./StateBoundary";

type D = {
	gaps?: { kind: string; description: string }[];
	status?: string;
	v?: number;
};
const base = {
	refetch: vi.fn(),
	error: null,
	isError: false,
	isPending: false,
	data: undefined,
};

describe("StateBoundary", () => {
	it("shows loading", () => {
		render(
			<StateBoundary<D> query={{ ...base, isPending: true }}>
				{() => <p>ok</p>}
			</StateBoundary>,
		);
		expect(screen.getByText(/Loading/)).toBeInTheDocument();
	});
	it("shows the error with a retry that refetches", () => {
		const refetch = vi.fn();
		render(
			<StateBoundary<D>
				query={{
					...base,
					refetch,
					isError: true,
					error: new ApiError(500, "boom"),
				}}
			>
				{() => <p>ok</p>}
			</StateBoundary>,
		);
		expect(screen.getByRole("alert")).toHaveTextContent("boom");
		fireEvent.click(screen.getByText("Retry"));
		expect(refetch).toHaveBeenCalled();
	});
	it("renders children with data, gaps and the placeholder banner", () => {
		const data: D = {
			status: "placeholder",
			gaps: [{ kind: "outlook_missing", description: "no outlook" }],
			v: 1,
		};
		render(
			<StateBoundary<D> query={{ ...base, data }}>
				{(d) => <p>value {d.v}</p>}
			</StateBoundary>,
		);
		expect(screen.getByText("value 1")).toBeInTheDocument();
		expect(screen.getByTestId("gaps")).toHaveTextContent("no outlook");
		expect(screen.getByTestId("placeholder-banner")).toHaveTextContent(
			"Illustrative, not computed",
		);
	});
	it("shows the empty notice", () => {
		render(
			<StateBoundary<D> query={{ ...base, data: {} }} isEmpty={() => true}>
				{() => <p>x</p>}
			</StateBoundary>,
		);
		expect(screen.getByText("Nothing to show.")).toBeInTheDocument();
	});
});
