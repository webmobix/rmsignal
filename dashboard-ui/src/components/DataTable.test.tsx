import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
	createColumnHelper,
	DataTable,
	type tableFeaturesConfig,
} from "./DataTable";

type Row = { name: string; aum: number };
const helper = createColumnHelper<typeof tableFeaturesConfig, Row>();
const columns = helper.columns([
	helper.accessor("name", { header: "Name" }),
	helper.accessor("aum", { header: "AuM" }),
]);
const data: Row[] = [
	{ name: "B", aum: 2 },
	{ name: "A", aum: 9 },
	{ name: "C", aum: 5 },
];
const names = () =>
	screen
		.getAllByRole("row")
		.slice(1)
		.map((r) => r.firstChild?.textContent);

describe("DataTable", () => {
	it("sorts by a column on click and reports the order", () => {
		let seen: Row[] = [];
		render(
			<DataTable
				columns={columns}
				data={data}
				onSortChange={(r) => {
					seen = r;
				}}
			/>,
		);
		fireEvent.click(screen.getByText("AuM"));
		expect(names()).toEqual(["A", "C", "B"]);
		expect(seen.map((r) => r.name)).toEqual(["A", "C", "B"]);
		fireEvent.click(screen.getByText("AuM"));
		expect(names()).toEqual(["B", "C", "A"]);
	});
	it("shows the empty state", () => {
		render(<DataTable columns={columns} data={[]} empty={<p>none</p>} />);
		expect(screen.getByText("none")).toBeInTheDocument();
	});
});
