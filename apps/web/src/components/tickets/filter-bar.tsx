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

const PLATFORM_OPTIONS: { value: string | "all"; label: string }[] = [
	{ value: "all", label: "All Platforms" },
	{ value: "shopify", label: "Shopify" },
	{ value: "woocommerce", label: "WooCommerce" },
	{ value: "amazon", label: "Amazon" },
	{ value: "mock", label: "Mock" },
];

interface FilterBarProps {
	current: TicketStatus | "all";
	onChange: (status: TicketStatus | "all") => void;
	platform: string | "all";
	onPlatformChange: (platform: string | "all") => void;
}

export function FilterBar({ current, onChange, platform, onPlatformChange }: FilterBarProps) {
	return (
		<div className="space-y-3">
			{/* Status filter */}
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

			{/* Platform filter */}
			<div className="flex gap-2 flex-wrap">
				{PLATFORM_OPTIONS.map((opt) => (
					<button
						key={opt.value}
						type="button"
						onClick={() => onPlatformChange(opt.value)}
						className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
							platform === opt.value
								? "bg-slate-700 text-white shadow-sm"
								: "bg-white text-slate-500 border border-slate-200 hover:bg-slate-50"
						}`}
					>
						{opt.label}
					</button>
				))}
			</div>
		</div>
	);
}
