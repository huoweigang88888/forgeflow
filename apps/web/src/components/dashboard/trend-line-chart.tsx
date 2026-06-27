"use client";

import type { TrendPoint } from "@/types";
import { useTranslation } from "react-i18next";
import {
	CartesianGrid,
	Legend,
	Line,
	LineChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";

interface TrendLineChartProps {
	data: TrendPoint[];
	days: number;
	onDaysChange: (days: number) => void;
}

export function TrendLineChart({
	data,
	days,
	onDaysChange,
}: TrendLineChartProps) {
	const { t } = useTranslation();

	if (!data || data.length === 0) {
		return (
			<div className="bg-white rounded-xl border border-slate-200 p-5">
				<div className="flex items-center justify-between mb-4">
					<h3 className="text-sm font-semibold text-slate-700">
						{t("charts.autoResolveRateTrend")}
					</h3>
					<div className="flex gap-1">
						{[7, 30].map((d) => (
							<button
								type="button"
								key={d}
								onClick={() => onDaysChange(d)}
								className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
									days === d
										? "bg-brand-100 text-brand-700"
										: "text-slate-500 hover:bg-slate-100"
								}`}
							>
								{d === 7 ? t("charts.days7") : t("charts.days30")}
							</button>
						))}
					</div>
				</div>
				<p className="text-sm text-slate-400 text-center py-8">
					{t("charts.noTrendData")}
				</p>
			</div>
		);
	}

	return (
		<div className="bg-white rounded-xl border border-slate-200 p-5">
			<div className="flex items-center justify-between mb-4">
				<h3 className="text-sm font-semibold text-slate-700">
					{t("charts.autoResolveRateTrend")}
				</h3>
				<div className="flex gap-1">
					{[7, 30].map((d) => (
						<button
							type="button"
							key={d}
							onClick={() => onDaysChange(d)}
							className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
								days === d
									? "bg-brand-100 text-brand-700"
									: "text-slate-500 hover:bg-slate-100"
							}`}
						>
							{d === 7 ? t("charts.days7") : t("charts.days30")}
						</button>
					))}
				</div>
			</div>
			<ResponsiveContainer width="100%" height={240}>
				<LineChart data={data}>
					<CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
					<XAxis
						dataKey="date"
						tick={{ fontSize: 11 }}
						tickFormatter={(v: string) => v.slice(5)}
					/>
					<YAxis
						tick={{ fontSize: 11 }}
						domain={[0, 100]}
						tickFormatter={(v: number) => `${v}%`}
					/>
					<Tooltip
						formatter={(value) => [
							`${Number(value)}%`,
							t("charts.resolutionRate"),
						]}
						labelFormatter={(label) => t("charts.dateLabel", { label })}
					/>
					<Legend />
					<Line
						type="monotone"
						dataKey="rate"
						stroke="#6366f1"
						strokeWidth={2}
						dot={{ r: 3 }}
						name={t("charts.autoResolveRate")}
					/>
				</LineChart>
			</ResponsiveContainer>
		</div>
	);
}
