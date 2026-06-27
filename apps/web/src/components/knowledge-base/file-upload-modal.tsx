"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileUp, X } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { uploadPolicyFile } from "@/lib/policies";

interface FileUploadModalProps {
	isOpen: boolean;
	onClose: () => void;
}

export function FileUploadModal({ isOpen, onClose }: FileUploadModalProps) {
	const [title, setTitle] = useState("");
	const [category, setCategory] = useState("");
	const [tags, setTags] = useState("");
	const [file, setFile] = useState<File | null>(null);
	const [dragOver, setDragOver] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);
	const queryClient = useQueryClient();
	const { t } = useTranslation();

	const uploadMutation = useMutation({
		mutationFn: async () => {
			if (!file) throw new Error("No file selected");
			return uploadPolicyFile(
				file,
				title || file.name.replace(/\.[^.]+$/, ""),
				category || undefined,
				tags ? tags.split(",").map((tag) => tag.trim()) : undefined,
			);
		},
		onSuccess: (data) => {
			queryClient.invalidateQueries({ queryKey: ["policies"] });
			onClose();
			resetForm();
		},
	});

	const resetForm = () => {
		setTitle("");
		setCategory("");
		setTags("");
		setFile(null);
	};

	const handleDrop = (e: React.DragEvent) => {
		e.preventDefault();
		setDragOver(false);
		const droppedFile = e.dataTransfer.files[0];
		if (droppedFile) {
			setFile(droppedFile);
			if (!title) setTitle(droppedFile.name.replace(/\.[^.]+$/, ""));
		}
	};

	const isAcceptedFile = (f: File) => {
		const ext = f.name.toLowerCase().split(".").pop();
		return ext && ["pdf", "md", "txt", "markdown"].includes(ext);
	};

	if (!isOpen) return null;

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
			<div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
				<div className="flex items-center justify-between mb-4">
					<h2 className="text-lg font-semibold text-slate-900">
						{t("knowledgeBase.uploadPolicyDoc")}
					</h2>
					<button
						type="button"
						onClick={onClose}
						className="p-1 text-slate-400 hover:text-slate-600 rounded"
					>
						<X size={20} />
					</button>
				</div>

				{/* Drop zone */}
				<div
					className={`border-2 border-dashed rounded-xl p-8 text-center mb-4 transition-colors ${
						dragOver
							? "border-brand-500 bg-brand-50"
							: file
								? "border-green-300 bg-green-50"
								: "border-slate-300 hover:border-slate-400"
					}`}
					onDragOver={(e) => {
						e.preventDefault();
						setDragOver(true);
					}}
					onDragLeave={() => setDragOver(false)}
					onDrop={handleDrop}
					onClick={() => fileInputRef.current?.click()}
					onKeyDown={(e) => {
						if (e.key === "Enter" || e.key === " ") {
							fileInputRef.current?.click();
						}
					}}
				>
					<FileUp
						size={32}
						className={`mx-auto mb-2 ${
							file ? "text-green-500" : "text-slate-400"
						}`}
					/>
					{file ? (
						<div>
							<p className="text-sm font-medium text-green-700">{file.name}</p>
							<p className="text-xs text-green-500 mt-1">
								{t("knowledgeBase.fileSizeChange", {
									size: (file.size / 1024).toFixed(1),
								})}
							</p>
						</div>
					) : (
						<div>
							<p className="text-sm text-slate-600">
								{t("knowledgeBase.dropFile")}
							</p>
							<p className="text-xs text-slate-400 mt-1">
								{t("knowledgeBase.supportsFormats")}
							</p>
						</div>
					)}
					<input
						ref={fileInputRef}
						type="file"
						accept=".pdf,.md,.txt,.markdown"
						className="hidden"
						onChange={(e) => {
							const f = e.target.files?.[0];
							if (f && isAcceptedFile(f)) {
								setFile(f);
								if (!title) setTitle(f.name.replace(/\.[^.]+$/, ""));
							}
						}}
					/>
				</div>

				{/* Metadata form */}
				<div className="space-y-3 mb-4">
					<div>
						<label
							htmlFor="upload-title"
							className="block text-xs font-medium text-slate-600 mb-1"
						>
							{t("knowledgeBase.titleLabel")}
						</label>
						<input
							id="upload-title"
							type="text"
							value={title}
							onChange={(e) => setTitle(e.target.value)}
							placeholder={t("knowledgeBase.titlePlaceholderShort")}
							className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
						/>
					</div>
					<div className="grid grid-cols-2 gap-3">
						<div>
							<label
								htmlFor="upload-category"
								className="block text-xs font-medium text-slate-600 mb-1"
							>
								{t("knowledgeBase.categoryLabel")}
							</label>
							<select
								id="upload-category"
								value={category}
								onChange={(e) => setCategory(e.target.value)}
								className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
							>
								<option value="">{t("knowledgeBase.categoryNone")}</option>
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
						<div>
							<label
								htmlFor="upload-tags"
								className="block text-xs font-medium text-slate-600 mb-1"
							>
								{t("knowledgeBase.tagsCommaSeparated")}
							</label>
							<input
								id="upload-tags"
								type="text"
								value={tags}
								onChange={(e) => setTags(e.target.value)}
								placeholder={t("knowledgeBase.tagsPlaceholderShort")}
								className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
							/>
						</div>
					</div>
				</div>

				{/* Actions */}
				<div className="flex gap-3 justify-end">
					<button
						type="button"
						onClick={onClose}
						className="px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50"
					>
						{t("common.cancel")}
					</button>
					<button
						type="button"
						onClick={() => uploadMutation.mutate()}
						disabled={!file || uploadMutation.isPending}
						className="px-4 py-2 text-sm font-medium text-white bg-brand-600 rounded-lg hover:bg-brand-700 disabled:opacity-50"
					>
						{uploadMutation.isPending
							? t("common.uploading")
							: t("common.upload")}
					</button>
				</div>

				{uploadMutation.isError && (
					<p className="text-xs text-red-600 mt-2">
						{t("knowledgeBase.uploadFailed", {
							error: String(uploadMutation.error),
						})}
					</p>
				)}
			</div>
		</div>
	);
}
