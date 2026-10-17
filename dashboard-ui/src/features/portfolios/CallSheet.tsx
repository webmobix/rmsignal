import type { Schemas } from "#/api/client";
import { useData } from "#/api/queries";
import { GapNotice, StateBoundary } from "#/components/StateBoundary";
import { fmtDate } from "#/lib/format";
import {
	BankViewCard,
	CashCard,
	ConversationCard,
	EventsCard,
	MandateCard,
	OwnershipCard,
	PerformanceCard,
} from "./callsheetSections";

export type CallSheetData = Schemas["CallSheet"];

/** The section order and the question each one answers. */
export const SECTION_QUESTIONS = [
	["performance", "How am I doing?"],
	["mandate", "Am I within my mandate?"],
	["ownership", "What do I own?"],
	["bank_view", "What does the bank think?"],
	["events", "What is happening?"],
	["cash_credit", "How are my cash and credit?"],
	["conversation", "When did we last speak?"],
] as const;

export function Section({
	id,
	question,
	gaps,
	children,
}: {
	id: string;
	question: string;
	gaps: Schemas["Gap"][] | undefined;
	children: React.ReactNode;
}) {
	return (
		<section
			className="mt-10 min-w-0"
			aria-labelledby={`cs-${id}`}
			data-testid={`cs-${id}`}
		>
			<h2 id={`cs-${id}`} className="mb-3 text-xl">
				{question}
			</h2>
			<GapNotice gaps={gaps} />
			{children}
		</section>
	);
}

export function CallSheetBody({ sheet }: { sheet: CallSheetData }) {
	const body = {
		performance: <PerformanceCard s={sheet.performance} />,
		mandate: <MandateCard s={sheet.mandate} />,
		ownership: <OwnershipCard s={sheet.ownership} />,
		bank_view: <BankViewCard s={sheet.bank_view} asOf={sheet.as_of} />,
		events: <EventsCard s={sheet.events} />,
		cash_credit: <CashCard s={sheet.cash_credit} />,
		conversation: (
			<ConversationCard s={sheet.conversation} clientId={sheet.client_id} />
		),
	};
	return (
		<div data-testid="call-sheet" className="min-w-0 break-words">
			<p className="mt-5 text-ink-muted">
				Call sheet as of{" "}
				<span className="num font-medium text-ink-2">
					{fmtDate(sheet.as_of)}
				</span>
				{" · "}
				{sheet.client_name} · {sheet.portfolio_name}
			</p>
			{SECTION_QUESTIONS.map(([key, question]) => (
				<Section key={key} id={key} question={question} gaps={sheet[key].gaps}>
					{body[key]}
				</Section>
			))}
		</div>
	);
}

/** Loads the call sheet when it is mounted, so the portfolio page does not pay for it until the tab opens. */
export function CallSheet({ portfolioId }: { portfolioId: string }) {
	const query = useData<CallSheetData>(`/portfolios/${portfolioId}/call-sheet`);
	return (
		<StateBoundary query={query} label="Loading call sheet" hideGaps>
			{(sheet) => <CallSheetBody sheet={sheet} />}
		</StateBoundary>
	);
}
