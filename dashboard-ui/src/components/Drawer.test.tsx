import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Drawer } from "./Drawer";

describe("Drawer", () => {
	it("renders nothing when closed", () => {
		render(
			<Drawer open={false} onClose={() => {}} title="T">
				x
			</Drawer>,
		);
		expect(screen.queryByRole("dialog")).toBeNull();
	});
	it("closes on Escape, the close control and the backdrop", () => {
		const onClose = vi.fn();
		render(
			<Drawer open onClose={onClose} title="T">
				body
			</Drawer>,
		);
		fireEvent.keyDown(document, { key: "Escape" });
		fireEvent.click(screen.getByLabelText("Close"));
		fireEvent.click(screen.getByTestId("drawer-backdrop"));
		expect(onClose).toHaveBeenCalledTimes(3);
		expect(screen.getByText("body")).toBeInTheDocument();
	});
});
