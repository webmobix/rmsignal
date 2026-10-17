import { type ReactNode, useEffect, useRef } from "react";

/** Right-hand drawer. Closes on Escape, the close control, or a click outside. */
export function Drawer({
	open,
	onClose,
	title,
	eyebrow,
	children,
}: {
	open: boolean;
	onClose: () => void;
	title: ReactNode;
	eyebrow?: ReactNode;
	children: ReactNode;
}) {
	const panel = useRef<HTMLElement>(null);
	useEffect(() => {
		if (!open) return;
		const onKey = (event: KeyboardEvent) => {
			if (event.key === "Escape") onClose();
		};
		document.addEventListener("keydown", onKey);
		panel.current?.focus();
		return () => document.removeEventListener("keydown", onKey);
	}, [open, onClose]);
	if (!open) return null;
	return (
		<div className="fixed inset-0 z-40">
			<button
				type="button"
				aria-label="Close drawer"
				data-testid="drawer-backdrop"
				onClick={onClose}
				className="absolute inset-0 bg-navy-950/25"
			/>
			<aside
				ref={panel}
				role="dialog"
				aria-modal="true"
				aria-label="Evidence"
				tabIndex={-1}
				className="absolute inset-y-0 right-0 w-[min(560px,100vw)] overflow-y-auto border-l border-rule bg-canvas px-6 pb-10 pt-5 shadow-[-12px_0_32px_-24px] outline-none"
			>
				<div className="flex items-start justify-between gap-4">
					<div>
						{eyebrow ? <div className="eyebrow mb-2">{eyebrow}</div> : null}
						<h2 className="text-xl leading-tight">{title}</h2>
					</div>
					<button
						type="button"
						onClick={onClose}
						aria-label="Close"
						className="-mr-2 px-2 py-1 text-xl leading-none text-ink-muted hover:text-navy-950"
					>
						×
					</button>
				</div>
				<div className="mt-5">{children}</div>
			</aside>
		</div>
	);
}
