"use client";

import type { TicketStatus } from "@/types";
import { useTranslation } from "react-i18next";

interface FilterBarProps {
	current: TicketStatus | "all";
	onChange: (status: TicketStatus | "all") => void;
	platform: string | "all";
	onPlatformChange: (platform: string | "all") => void;
}

export function FilterBar({
	current,
	onChange,
	platform,
	onPlatformChange,
}: FilterBarProps) {
	const { t } = useTranslation();

	const STATUS_OPTIONS: { value: TicketStatus | "all"; label: string }[] = [
		{ value: "all", label: t("tickets.filterAll") },
		{ value: "processing", label: t("tickets.filterProcessing") },
		{ value: "pending_approval", label: t("tickets.filterPendingApproval") },
		{ value: "resolved", label: t("tickets.filterResolved") },
		{ value: "escalated", label: t("tickets.filterEscalated") },
		{ value: "failed", label: t("tickets.filterFailed") },
	];

	const PLATFORM_OPTIONS: { value: string | "all"; label: string }[] = [
		{ value: "all", label: t("platform.allPlatforms") },
		{ value: "shopify", label: t("platform.shopify") },
		{ value: "woocommerce", label: t("platform.woocommerce") },
		{ value: "amazon", label: t("platform.amazon") },
		{ value: "mock", label: t("platform.mock") },
	];

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
