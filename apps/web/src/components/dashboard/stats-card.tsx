"use client";

import type { LucideIcon } from "lucide-react";

interface StatsCardProps {
	label: string;
	value: string | number;
	subtext?: string;
	icon?: LucideIcon;
	trend?: "up" | "down" | "neutral";
}

export function StatsCard({
	label,
	value,
	subtext,
	icon: Icon,
	trend,
}: StatsCardProps) {
	return (
		<div className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-sm transition-shadow">
			<div className="flex items-start justify-between">
				<div className="flex-1">
					<p className="text-sm text-slate-500 mb-1">{label}</p>
					<p className="text-3xl font-bold text-slate-900">{value}</p>
					{subtext && <p className="text-xs text-slate-400 mt-1">{subtext}</p>}
				</div>
				{Icon && (
					<div
						className={`p-2 rounded-lg ${
							trend === "up"
								? "bg-green-50 text-green-600"
								: trend === "down"
									? "bg-red-50 text-red-600"
									: "bg-brand-50 text-brand-600"
						}`}
					>
						<Icon size={20} />
					</div>
				)}
			</div>
		</div>
	);
}
