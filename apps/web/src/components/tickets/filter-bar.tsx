"use client";

import type { TicketStatus } from "@/types";

const STATUS_OPTIONS: { value: TicketStatus | "all"; label: string }[] = [
	{ value: "all", label: "All" },
	{ value: "processing", label: "Processing" },
	{ value: "pending_approval", label: "Pending Approval" },
	{ value: "resolved", label: "Resolved" },
	{ value: "escalated", label: "Escalated" },
	{ value: "failed", label: "Failed" },
];

interface FilterBarProps {
	current: TicketStatus | "all";
	onChange: (status: TicketStatus | "all") => void;
}

export function FilterBar({ current, onChange }: FilterBarProps) {
	return (
		<div className="flex gap-2 flex-wrap">
			{STATUS_OPTIONS.map((opt) => (
				<button
					key={opt.value}
					type="button"
					onClick={() => onChange(opt.value)}
					className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
						current === opt.value
							? "bg-brand-600 text-white shadow-sm"
							: "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
					}`}
				>
					{opt.label}
				</button>
			))}
		</div>
	);
}
