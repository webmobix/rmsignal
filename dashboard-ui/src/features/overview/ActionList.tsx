import { useMemo } from "react";
import type { ApiAction } from "#/api/queries";
import {
	createColumnHelper,
	DataTable,
	type tableFeaturesConfig,
} from "#/components/DataTable";
import { IdLink, OpenActionLink } from "#/components/IdLink";
import { TierBadge } from "#/components/TierBadge";
import { fmtDate, titleCase } from "#/lib/format";

const helper = createColumnHelper<typeof tableFeaturesConfig, ApiAction>();

const columns = helper.columns([
	helper.accessor("rank", {
		header: "#",
		cell: ({ row }) => (
			<span className="num text-ink-muted">{row.original.rank}</span>
		),
	}),
	helper.accessor("title", {
		header: "Action",
		cell: ({ row }) => (
			<div className="max-w-[48ch]">
				<OpenActionLink id={row.original.action_id}>
					{row.original.title}
				</OpenActionLink>
			</div>
		),
	}),
	helper.accessor("client_name", {
		header: "Client",
		cell: ({ row }) => (
			<div>
				<IdLink id={row.original.client_id}>{row.original.client_name}</IdLink>
			</div>
		),
	}),
	helper.accessor("category", {
		header: "Category",
		cell: ({ row }) => titleCase(row.original.category),
	}),
	helper.accessor("importance", {
		header: "Importance",
		cell: ({ row }) => <TierBadge tier={row.original.importance} />,
	}),
	helper.accessor("horizon", {
		header: "Horizon",
		cell: ({ row }) => titleCase(row.original.horizon),
	}),
	helper.accessor("due_date", {
		header: "Due",
		cell: ({ row }) => (
			<span className="num">{fmtDate(row.original.due_date)}</span>
		),
	}),
]);

export function ActionTable({
	actions,
	empty,
}: {
	actions: ApiAction[];
	empty?: string;
}) {
	const data = useMemo(() => actions, [actions]);
	return (
		<DataTable
			columns={columns}
			data={data}
			initialSort={{ id: "rank", desc: false }}
			rowId={(a) => a.action_id}
			empty={
				<p className="py-6 text-sm text-ink-muted">
					{empty ?? "No actions match."}
				</p>
			}
		/>
	);
}
