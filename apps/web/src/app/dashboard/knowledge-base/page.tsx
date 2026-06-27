"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
	BookOpen,
	ChevronLeft,
	ChevronRight,
	Plus,
	Search,
	Upload,
	X,
} from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { FileUploadModal } from "@/components/knowledge-base/file-upload-modal";
import { PolicyCard } from "@/components/knowledge-base/policy-card";
import { SearchConsole } from "@/components/knowledge-base/search-console";
import {
	createPolicy,
	deletePolicy,
	listPolicies,
	searchPolicies,
} from "@/lib/policies";
import { useKnowledgeBaseStore } from "@/lib/store";
import type { PolicyDocument, PolicySearchHit } from "@/types";

export default function KnowledgeBasePage() {
	const queryClient = useQueryClient();
	const {
		searchQuery,
		selectedCategory,
		isUploadOpen,
		page,
		setSearchQuery,
		setSelectedCategory,
		setUploadOpen,
		setPage,
	} = useKnowledgeBaseStore();
	const { t } = useTranslation();

	const [deletingId, setDeletingId] = useState<string | null>(null);
	const [showSearchConsole, setShowSearchConsole] = useState(false);
	const [uploadTab, setUploadTab] = useState<"text" | "file">("text");

	const CATEGORIES = [
		{ value: null, label: t("knowledgeBase.categoryAll") },
		{ value: "shipping", label: t("knowledgeBase.categoryShipping") },
		{ value: "refund", label: t("knowledgeBase.categoryRefund") },
		{ value: "exchange", label: t("knowledgeBase.categoryExchange") },
		{ value: "general", label: t("knowledgeBase.categoryGeneral") },
	];

	// ── List policies ──
	const {
		data: listData,
		isLoading,
		isError,
	} = useQuery({
		queryKey: ["policies", { category: selectedCategory, page }],
		queryFn: () =>
			listPolicies({
				page,
				page_size: 12,
				category: selectedCategory ?? undefined,
			}),
		enabled: searchQuery.length === 0,
	});

	// ── Search ──
	const { data: searchData, isLoading: isSearching } = useQuery({
		queryKey: ["policies-search", searchQuery, selectedCategory],
		queryFn: () =>
			searchPolicies(searchQuery, {
				category: selectedCategory ?? undefined,
				limit: 12,
			}),
		enabled: searchQuery.length > 0,
	});

	const policies: PolicyDocument[] = listData?.policies ?? [];
	const searchHits: PolicySearchHit[] = searchData?.hits ?? [];
	const total = searchQuery ? (searchData?.total ?? 0) : (listData?.total ?? 0);
	const totalPages = Math.max(1, Math.ceil(total / 12));

	// ── Delete ──
	const handleDelete = async (id: string) => {
		setDeletingId(id);
		try {
			await deletePolicy(id);
			queryClient.invalidateQueries({ queryKey: ["policies"] });
			queryClient.invalidateQueries({ queryKey: ["policies-search"] });
		} catch {
			// Keep UI stable on error
		} finally {
			setDeletingId(null);
		}
	};

	const isSearchActive = searchQuery.length > 0;

	return (
		<div>
			{/* Header */}
			<div className="flex items-center justify-between mb-2">
				<div>
					<h1 className="text-2xl font-bold text-slate-900">
						{t("knowledgeBase.title")}
					</h1>
					<p className="text-slate-500 mt-1">{t("knowledgeBase.subtitle")}</p>
				</div>
				<button
					type="button"
					onClick={() => setUploadOpen(true)}
					className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 transition-colors"
				>
					<Plus size={16} />
					{t("knowledgeBase.uploadPolicy")}
				</button>
			</div>

			{/* Search + Filter */}
			<div className="flex items-center gap-3 mb-6">
				<div className="relative flex-1 max-w-md">
					<Search
						size={16}
						className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
					/>
					<input
						type="text"
						value={searchQuery}
						onChange={(e) => {
							setSearchQuery(e.target.value);
							setPage(1);
						}}
						placeholder={t("knowledgeBase.searchPlaceholder")}
						className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-8 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
					/>
					{searchQuery && (
						<button
							type="button"
							onClick={() => setSearchQuery("")}
							className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
						>
							<X size={14} />
						</button>
					)}
				</div>

				{/* Category tabs */}
				<div className="flex gap-1 bg-slate-100 rounded-lg p-1">
					{CATEGORIES.map((cat) => (
						<button
							key={cat.label}
							type="button"
							onClick={() => setSelectedCategory(cat.value)}
							className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
								selectedCategory === cat.value
									? "bg-white text-slate-900 shadow-sm"
									: "text-slate-500 hover:text-slate-700"
							}`}
						>
							{cat.label}
						</button>
					))}
				</div>
			</div>

			{/* Search Console (Debug) */}
			<div className="mb-6">
				<SearchConsole
					isOpen={showSearchConsole}
					onToggle={() => setShowSearchConsole(!showSearchConsole)}
				/>
			</div>

			{/* Loading */}
			{(isLoading || isSearching) && (
				<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
					<p className="text-slate-400">
						{isSearchActive
							? t("knowledgeBase.searchingPolicies")
							: t("knowledgeBase.loadingPolicies")}
					</p>
				</div>
			)}

			{/* Error */}
			{isError && (
				<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
					<p className="text-red-500">{t("knowledgeBase.failedToLoad")}</p>
				</div>
			)}

			{/* Empty */}
			{!isLoading && !isSearching && !isError && (
				<>
					{!isSearchActive && policies.length === 0 && (
						<div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
							<BookOpen size={40} className="mx-auto text-slate-300 mb-4" />
							<p className="text-slate-500 font-medium">
								{t("knowledgeBase.noPolicies")}
							</p>
							<p className="text-sm text-slate-400 mt-1">
								{t("knowledgeBase.uploadHint")}
							</p>
						</div>
					)}

					{isSearchActive && searchHits.length === 0 && (
						<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
							<p className="text-slate-400">
								{t("knowledgeBase.noResults", { query: searchQuery })}
							</p>
						</div>
					)}

					{/* Policy Cards Grid */}
					{((!isSearchActive && policies.length > 0) ||
						(isSearchActive && searchHits.length > 0)) && (
						<>
							<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
								{isSearchActive
									? searchHits.map((hit) => (
											<PolicyCard
												key={hit.policy.id}
												policy={hit.policy}
												similarity={hit.similarity}
												onDelete={handleDelete}
												isDeleting={deletingId === hit.policy.id}
											/>
										))
									: policies.map((p) => (
											<PolicyCard
												key={p.id}
												policy={p}
												onDelete={handleDelete}
												isDeleting={deletingId === p.id}
											/>
										))}
							</div>

							{/* Pagination */}
							{!isSearchActive && totalPages > 1 && (
								<div className="flex items-center justify-center gap-2 mt-6">
									<button
										type="button"
										onClick={() => setPage(Math.max(1, page - 1))}
										disabled={page <= 1}
										className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
									>
										<ChevronLeft size={16} />
									</button>
									<span className="text-sm text-slate-500">
										{t("knowledgeBase.pageOf", { page, totalPages })}
									</span>
									<button
										type="button"
										onClick={() => setPage(Math.min(totalPages, page + 1))}
										disabled={page >= totalPages}
										className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
									>
										<ChevronRight size={16} />
									</button>
								</div>
							)}
						</>
					)}
				</>
			)}

			{/* Upload Modal */}
			{isUploadOpen && uploadTab === "text" && (
				<UploadModal
					onClose={() => setUploadOpen(false)}
					onCreated={() => {
						setUploadOpen(false);
						queryClient.invalidateQueries({ queryKey: ["policies"] });
					}}
					onSwitchToFile={() => setUploadTab("file")}
				/>
			)}
			{isUploadOpen && uploadTab === "file" && (
				<FileUploadModal
					isOpen={isUploadOpen}
					onClose={() => {
						setUploadOpen(false);
						setUploadTab("text");
					}}
				/>
			)}
		</div>
	);
}

// ── Upload Modal ──

function UploadModal({
	onClose,
	onCreated,
	onSwitchToFile,
}: {
	onClose: () => void;
	onCreated: () => void;
	onSwitchToFile: () => void;
}) {
	const [title, setTitle] = useState("");
	const [content, setContent] = useState("");
	const [category, setCategory] = useState("");
	const [tagsText, setTagsText] = useState("");
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const { t } = useTranslation();

	const handleSubmit = async () => {
		if (!title.trim() || !content.trim()) return;

		setIsSubmitting(true);
		setError(null);

		try {
			const tags = tagsText
				.split(",")
				.map((tag) => tag.trim())
				.filter(Boolean);

			await createPolicy({
				title: title.trim(),
				content: content.trim(),
				category: category || undefined,
				tags: tags.length > 0 ? tags : undefined,
			});

			onCreated();
		} catch (e) {
			setError(
				e instanceof Error ? e.message : t("knowledgeBase.createFailed"),
			);
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
			<div className="bg-white rounded-xl border border-slate-200 w-full max-w-lg mx-4 p-6 shadow-xl">
				<div className="flex items-center justify-between mb-4">
					<div className="flex items-center gap-3">
						<h2 className="text-lg font-semibold text-slate-900">
							{t("knowledgeBase.uploadPolicy")}
						</h2>
						{/* Tab switcher */}
						<div className="flex gap-1 bg-slate-100 rounded-lg p-0.5">
							<button
								type="button"
								className="px-2.5 py-1 text-xs font-medium rounded-md bg-white text-slate-900 shadow-sm"
							>
								{t("knowledgeBase.pasteText")}
							</button>
							<button
								type="button"
								onClick={onSwitchToFile}
								className="px-2.5 py-1 text-xs font-medium rounded-md text-slate-500 hover:text-slate-700"
							>
								{t("knowledgeBase.uploadFile")}
							</button>
						</div>
					</div>
					<button
						type="button"
						onClick={onClose}
						className="text-slate-400 hover:text-slate-600"
					>
						<X size={20} />
					</button>
				</div>

				<div className="space-y-4">
					{/* Title */}
					<div>
						<label
							htmlFor="policy-title"
							className="block text-sm font-medium text-slate-700 mb-1"
						>
							{t("knowledgeBase.titleRequired")}
						</label>
						<input
							id="policy-title"
							type="text"
							value={title}
							onChange={(e) => setTitle(e.target.value)}
							placeholder={t("knowledgeBase.titlePlaceholder")}
							className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
							maxLength={500}
						/>
					</div>

					{/* Category */}
					<div>
						<label
							htmlFor="policy-category"
							className="block text-sm font-medium text-slate-700 mb-1"
						>
							{t("knowledgeBase.categoryLabel")}
						</label>
						<select
							id="policy-category"
							value={category}
							onChange={(e) => setCategory(e.target.value)}
							className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
						>
							<option value="">{t("common.selectCategory")}</option>
							<option value="shipping">
								{t("knowledgeBase.categoryShipping")}
							</option>
							<option value="refund">
								{t("knowledgeBase.categoryRefund")}
							</option>
							<option value="exchange">
								{t("knowledgeBase.categoryExchange")}
							</option>
							<option value="general">
								{t("knowledgeBase.categoryGeneral")}
							</option>
						</select>
					</div>

					{/* Content */}
					<div>
						<label
							htmlFor="policy-content"
							className="block text-sm font-medium text-slate-700 mb-1"
						>
							{t("knowledgeBase.policyTextRequired")}
						</label>
						<textarea
							id="policy-content"
							value={content}
							onChange={(e) => setContent(e.target.value)}
							placeholder={t("knowledgeBase.policyTextPlaceholder")}
							rows={8}
							className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 resize-vertical"
							maxLength={50000}
						/>
						<p className="text-xs text-slate-400 mt-1">
							{t("knowledgeBase.charCount", {
								n: content.length.toLocaleString(),
							})}
						</p>
					</div>

					{/* Tags */}
					<div>
						<label
							htmlFor="policy-tags"
							className="block text-sm font-medium text-slate-700 mb-1"
						>
							{t("knowledgeBase.tagsLabel")}
						</label>
						<input
							id="policy-tags"
							type="text"
							value={tagsText}
							onChange={(e) => setTagsText(e.target.value)}
							placeholder={t("knowledgeBase.tagsPlaceholder")}
							className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
						/>
					</div>

					{/* Error */}
					{error && (
						<p className="text-sm text-red-500 bg-red-50 rounded-lg px-3 py-2">
							{error}
						</p>
					)}
				</div>

				{/* Actions */}
				<div className="flex justify-end gap-3 mt-6">
					<button
						type="button"
						onClick={onClose}
						disabled={isSubmitting}
						className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
					>
						{t("common.cancel")}
					</button>
					<button
						type="button"
						onClick={handleSubmit}
						disabled={isSubmitting || !title.trim() || !content.trim()}
						className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					>
						<Upload size={16} />
						{isSubmitting ? t("common.uploading") : t("common.upload")}
					</button>
				</div>
			</div>
		</div>
	);
}
