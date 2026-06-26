"use client";

import type { LLMCostPoint } from "@/types";
import {
	Bar,
	BarChart,
	CartesianGrid,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts";

interface LLMCostChartProps {
	data: LLMCostPoint[];
}

export function LLMCostChart({ data }: LLMCostChartProps) {
	const totalCost = data.reduce((sum, d) => sum + d.cost, 0);

	if (!data || data.length === 0) {
		return (
			<div className="bg-white rounded-xl border border-slate-200 p-5">
				<h3 className="text-sm font-semibold text-slate-700 mb-1">
					LLM Cost
				</h3>
				<p className="text-xs text-slate-400">Daily API costs</p>
				<p className="text-sm text-slate-400 text-center py-8">
					No cost data available yet.
				</p>
			</div>
		);
	}

	return (
		<div className="bg-white rounded-xl border border-slate-200 p-5">
			<div className="flex items-center justify-between mb-1">
				<h3 className="text-sm font-semibold text-slate-700">LLM Cost</h3>
				<span className="text-xs font-medium text-slate-500">
					Total: ${totalCost.toFixed(2)}
				</span>
			</div>
			<p className="text-xs text-slate-400 mb-4">Daily API costs</p>
			<ResponsiveContainer width="100%" height={200}>
				<BarChart data={data}>
					<CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
					<XAxis
						dataKey="date"
						tick={{ fontSize: 10 }}
						tickFormatter={(v: string) => v.slice(5)}
					/>
					<YAxis
						tick={{ fontSize: 10 }}
						tickFormatter={(v: number) => `$${v.toFixed(2)}`}
					/>
					<Tooltip
						formatter={(value) => [
							`$${Number(value).toFixed(4)}`,
							"Cost",
						]}
						labelFormatter={(label) => `Date: ${label}`}
					/>
					<Bar
						dataKey="cost"
						fill="#818cf8"
						radius={[4, 4, 0, 0]}
						name="LLM Cost"
					/>
				</BarChart>
			</ResponsiveContainer>
		</div>
	);
}
