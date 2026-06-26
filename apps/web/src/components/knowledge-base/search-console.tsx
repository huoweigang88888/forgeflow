"use client";

import type { SearchMode } from "@/lib/policies";
import { searchPolicies, searchPoliciesHybrid, searchPoliciesText } from "@/lib/policies";
import type { PolicySearchHit } from "@/types";
import { Search, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

interface SearchConsoleProps {
	isOpen: boolean;
	onToggle: () => void;
}

export function SearchConsole({ isOpen, onToggle }: SearchConsoleProps) {
	const [query, setQuery] = useState("");
	const [mode, setMode] = useState<SearchMode>("hybrid");
	const [threshold, setThreshold] = useState(0.1);
	const [results, setResults] = useState<PolicySearchHit[]>([]);
	const [total, setTotal] = useState(0);
	const [searching, setSearching] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleSearch = async () => {
		if (!query.trim()) return;
		setSearching(true);
		setError(null);
		try {
			let data: { hits: PolicySearchHit[]; total: number };
			const baseOptions = { limit: 10, threshold };

			switch (mode) {
				case "text":
					data = await searchPoliciesText(query, baseOptions);
					break;
				case "hybrid":
					data = await searchPoliciesHybrid(query, baseOptions);
					break;
				default:
					data = await searchPolicies(query, baseOptions);
			}
			setResults(data.hits);
			setTotal(data.total);
		} catch (e) {
			setError(String(e));
			setResults([]);
		} finally {
			setSearching(false);
		}
	};

	return (
		<div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
			<button
				type="button"
				onClick={onToggle}
				className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
			>
				<div className="flex items-center gap-2 text-sm font-medium text-slate-700">
					<SlidersHorizontal size={16} />
					Search Console
					<span className="text-xs text-slate-400 font-normal">(Debug)</span>
				</div>
				<span
					className={`text-xs text-slate-400 transition-transform ${
						isOpen ? "rotate-180" : ""
					}`}
				>
					▼
				</span>
			</button>

			{isOpen && (
				<div className="px-4 pb-4 border-t border-slate-100">
					{/* Search input + mode toggle */}
					<div className="flex gap-2 mt-3 mb-3">
						<input
							type="text"
							value={query}
							onChange={(e) => setQuery(e.target.value)}
							onKeyDown={(e) => e.key === "Enter" && handleSearch()}
							placeholder="Enter search query..."
							className="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
						/>
						<button
							type="button"
							onClick={handleSearch}
							disabled={searching || !query.trim()}
							className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50"
						>
							<Search size={14} />
							{searching ? "..." : "Search"}
						</button>
					</div>

					{/* Mode selector */}
					<div className="flex gap-2 mb-3">
						{(
							[
								["semantic", "Semantic"],
								["text", "Text"],
								["hybrid", "Hybrid"],
							] as [SearchMode, string][]
						).map(([m, label]) => (
							<button
								type="button"
								key={m}
								onClick={() => setMode(m)}
								className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
									mode === m
										? "bg-brand-100 text-brand-700"
										: "bg-slate-100 text-slate-600 hover:bg-slate-200"
								}`}
							>
								{label}
							</button>
						))}
					</div>

					{/* Threshold slider (semantic + hybrid only) */}
					{mode !== "text" && (
						<div className="flex items-center gap-3 mb-3">
							<span className="text-xs text-slate-500 shrink-0">
								Threshold: {threshold.toFixed(2)}
							</span>
							<input
								type="range"
								min={0}
								max={1}
								step={0.05}
								value={threshold}
								onChange={(e) => setThreshold(Number(e.target.value))}
								className="flex-1 h-1.5 accent-brand-600"
							/>
						</div>
					)}

					{/* Results */}
					{error && (
						<p className="text-xs text-red-600 mb-2">Error: {error}</p>
					)}
					{results.length > 0 && (
						<div>
							<p className="text-xs text-slate-400 mb-2">
								{total} result{total !== 1 ? "s" : ""}
							</p>
							<div className="space-y-2 max-h-80 overflow-y-auto">
								{results.map((hit, i) => (
									<div
										key={hit.policy.id || i}
										className="p-2 bg-slate-50 rounded-lg text-sm"
									>
										<div className="flex items-center justify-between mb-1">
											<span className="font-medium text-slate-800 text-xs truncate max-w-[70%]">
												{hit.policy.title}
											</span>
											<span className="text-xs font-mono text-brand-600">
												{hit.similarity.toFixed(4)}
											</span>
										</div>
										<p className="text-xs text-slate-500 line-clamp-2">
											{hit.policy.content?.slice(0, 200)}
										</p>
										<div className="flex gap-2 mt-1">
											{hit.policy.category && (
												<span className="text-[10px] px-1.5 py-0.5 bg-slate-200 rounded-full text-slate-600">
													{hit.policy.category}
												</span>
											)}
											<span className="text-[10px] text-slate-400">
												chunk #{hit.policy.chunk_index}
											</span>
										</div>
									</div>
								))}
							</div>
						</div>
					)}
					{!searching && query && results.length === 0 && !error && (
						<p className="text-xs text-slate-400 text-center py-4">
							No results found. Try a different query or mode.
						</p>
					)}
				</div>
			)}
		</div>
	);
}
