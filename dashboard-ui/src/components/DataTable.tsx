import type { RowData } from "@tanstack/react-table";
import {
	createColumnHelper,
	createSortedRowModel,
	rowSortingFeature,
	sortFn_alphanumeric,
	sortFn_text,
	tableFeatures,
	useTable,
} from "@tanstack/react-table";
import { type ReactNode, useEffect } from "react";

export const tableFeaturesConfig = tableFeatures({
	rowSortingFeature,
	sortedRowModel: createSortedRowModel(),
	sortFns: { alphanumeric: sortFn_alphanumeric, text: sortFn_text },
});

export { createColumnHelper };

type ColumnDefs<T extends RowData> = Parameters<
	typeof useTable<typeof tableFeaturesConfig, T>
>[0]["columns"];

/** Shared sortable table used by every list in the app. */
export function DataTable<T extends RowData>({
	columns,
	data,
	initialSort,
	empty,
	onSortChange,
	rowId,
}: {
	columns: ColumnDefs<T>;
	data: T[];
	initialSort?: { id: string; desc: boolean };
	empty?: ReactNode;
	onSortChange?: (rows: T[]) => void;
	rowId?: (row: T) => string;
}) {
	const table = useTable({
		features: tableFeaturesConfig,
		columns,
		data,
		initialState: { sorting: initialSort ? [initialSort] : [] },
		getRowId: rowId ? (row) => rowId(row) : undefined,
	});
	const rows = table.getRowModel().rows;
	const orderKey = rows.map((r) => r.id).join("|");
	// biome-ignore lint/correctness/useExhaustiveDependencies: fire only when the visible order changes
	useEffect(() => {
		onSortChange?.(rows.map((r) => r.original));
	}, [orderKey]);
	if (!rows.length)
		return <>{empty ?? <p className="py-6 text-ink-muted">No rows.</p>}</>;
	return (
		<div className="overflow-x-auto">
			<table className="data-table">
				<thead>
					{table.getHeaderGroups().map((group) => (
						<tr key={group.id}>
							{group.headers.map((header) => {
								const sorted = header.column.getIsSorted();
								return (
									<th
										key={header.id}
										aria-sort={
											sorted === "asc"
												? "ascending"
												: sorted === "desc"
													? "descending"
													: "none"
										}
									>
										{header.isPlaceholder ? null : (
											<button
												type="button"
												className="inline-flex items-center gap-1 uppercase"
												onClick={header.column.getToggleSortingHandler()}
											>
												<table.FlexRender header={header} />
												<span aria-hidden="true">
													{sorted === "asc"
														? "▲"
														: sorted === "desc"
															? "▼"
															: ""}
												</span>
											</button>
										)}
									</th>
								);
							})}
						</tr>
					))}
				</thead>
				<tbody>
					{rows.map((row) => (
						<tr key={row.id}>
							{row.getAllCells().map((cell) => (
								<td key={cell.id}>
									<table.FlexRender cell={cell} />
								</td>
							))}
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}
