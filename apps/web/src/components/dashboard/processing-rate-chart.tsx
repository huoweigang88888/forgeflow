"use client";

import type { ProcessingRatePoint } from "@/types";
import { useTranslation } from "react-i18next";
import {
	Area,
	AreaChart,
	CartesianGrid,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";

interface ProcessingRateChartProps {
	data: ProcessingRatePoint[];
}

export function ProcessingRateChart({ data }: ProcessingRateChartProps) {
	const { t } = useTranslation();
	// Calculate average tickets per hour
	const totalTickets = data.reduce((sum, d) => sum + d.count, 0);
	const avgRate =
		data.length > 0 ? (totalTickets / data.length).toFixed(1) : "0";

	if (!data || data.length === 0) {
		return (
			<div className="bg-white rounded-xl border border-slate-200 p-5">
				<h3 className="text-sm font-semibold text-slate-700 mb-1">
					{t("charts.processingRate")}
				</h3>
				<p className="text-xs text-slate-400">{t("charts.ticketsPerHour")}</p>
				<p className="text-sm text-slate-400 text-center py-8">
					{t("charts.noProcessingData")}
				</p>
			</div>
		);
	}

	return (
		<div className="bg-white rounded-xl border border-slate-200 p-5">
			<div className="flex items-center justify-between mb-1">
				<h3 className="text-sm font-semibold text-slate-700">
					{t("charts.processingRate")}
				</h3>
				<span className="text-xs font-medium text-slate-500">
					{t("charts.avgRate", { avgRate })}
				</span>
			</div>
			<p className="text-xs text-slate-400 mb-4">
				{t("charts.ticketsPerHour")}
			</p>
			<ResponsiveContainer width="100%" height={200}>
				<AreaChart data={data}>
					<CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
					<XAxis
						dataKey="hour"
						tick={{ fontSize: 10 }}
						tickFormatter={(v: string) => {
							const d = new Date(v);
							return d.toLocaleTimeString([], {
								hour: "2-digit",
								minute: "2-digit",
							});
						}}
					/>
					<YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
					<Tooltip
						formatter={(value) => [Number(value), t("charts.tickets")]}
						labelFormatter={(label) =>
							t("charts.hour", {
								label: new Date(String(label)).toLocaleString(),
							})
						}
					/>
					<Area
						type="monotone"
						dataKey="count"
						stroke="#6366f1"
						fill="#c7d2fe"
						strokeWidth={2}
						name={t("charts.tickets")}
					/>
				</AreaChart>
			</ResponsiveContainer>
		</div>
	);
}
