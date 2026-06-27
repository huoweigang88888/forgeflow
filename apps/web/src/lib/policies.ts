/**
 * ForgeFlow — Policy Document API Functions.
 *
 * Typed wrappers around the API client for all knowledge base operations.
 * Used by TanStack Query hooks in the Knowledge Base page.
 */

import type {
	PolicyCreateInput,
	PolicyDocument,
	PolicyListData,
	PolicySearchData,
	PolicyUpdateInput,
} from "@/types";
import { api } from "./api";

// ── Create ──

export async function createPolicy(
	input: PolicyCreateInput,
): Promise<PolicyDocument> {
	const res = await api.post<{
		code: number;
		data: { policy: PolicyDocument };
	}>("/api/v1/policies", input);
	return res.data.policy;
}

// ── List ──

export interface ListPoliciesParams {
	page?: number;
	page_size?: number;
	category?: string;
}

export async function listPolicies(
	params: ListPoliciesParams = {},
): Promise<PolicyListData> {
	const searchParams = new URLSearchParams();
	if (params.page) searchParams.set("page", String(params.page));
	if (params.page_size) searchParams.set("page_size", String(params.page_size));
	if (params.category) searchParams.set("category", params.category);

	const qs = searchParams.toString();
	const res = await api.get<{ code: number; data: PolicyListData }>(
		`/api/v1/policies${qs ? `?${qs}` : ""}`,
	);
	return res.data;
}

// ── Detail ──

export async function getPolicy(policyId: string): Promise<PolicyDocument> {
	const res = await api.get<{ code: number; data: { policy: PolicyDocument } }>(
		`/api/v1/policies/${policyId}`,
	);
	return res.data.policy;
}

// ── Update ──

export async function updatePolicy(
	policyId: string,
	input: PolicyUpdateInput,
): Promise<PolicyDocument> {
	const res = await api.put<{ code: number; data: { policy: PolicyDocument } }>(
		`/api/v1/policies/${policyId}`,
		input,
	);
	return res.data.policy;
}

// ── Delete ──

export async function deletePolicy(policyId: string): Promise<void> {
	await api.delete<{ code: number; data: { id: string } }>(
		`/api/v1/policies/${policyId}`,
	);
}

// ── Search ──

export interface SearchPoliciesOptions {
	category?: string;
	limit?: number;
	threshold?: number;
}

export async function searchPolicies(
	query: string,
	options: SearchPoliciesOptions = {},
): Promise<PolicySearchData> {
	const res = await api.post<{ code: number; data: PolicySearchData }>(
		"/api/v1/policies/search",
		{
			query,
			category: options.category,
			limit: options.limit ?? 5,
			threshold: options.threshold ?? 0.7,
		},
	);
	return res.data;
}

// ── File Upload ──

export interface FileUploadResult {
	source_document_id: string;
	chunk_count: number;
	total_chars: number;
}

export async function uploadPolicyFile(
	file: File,
	title: string,
	category?: string,
	tags?: string[],
): Promise<FileUploadResult> {
	const formData = new FormData();
	formData.append("file", file);
	formData.append("title", title);
	if (category) formData.append("category", category);
	if (tags) formData.append("tags", tags.join(","));

	const res = await api.post<{
		code: number;
		message: string;
		data: FileUploadResult;
	}>("/api/v1/policies/upload", formData);
	return res.data;
}

// ── Chunk Preview ──

export interface ChunkPreviewItem {
	chunk_index: number;
	title: string;
	preview_text: string;
	char_count: number;
	has_embedding: boolean;
	policy_id: string;
}

export interface ChunkListData {
	chunks: ChunkPreviewItem[];
	source_document_id: string;
	total_chunks: number;
}

export async function getChunks(
	sourceDocumentId: string,
): Promise<ChunkListData> {
	const res = await api.get<{ code: number; data: ChunkListData }>(
		`/api/v1/policies/${sourceDocumentId}/chunks`,
	);
	return res.data;
}

// ── Text Search ──

export async function searchPoliciesText(
	query: string,
	options: SearchPoliciesOptions = {},
): Promise<PolicySearchData> {
	const res = await api.post<{ code: number; data: PolicySearchData }>(
		"/api/v1/policies/search/text",
		{
			query,
			category: options.category,
			limit: options.limit ?? 10,
		},
	);
	return res.data;
}

// ── Hybrid Search ──

export interface HybridSearchOptions extends SearchPoliciesOptions {
	similarity_weight?: number;
	keyword_weight?: number;
}

export async function searchPoliciesHybrid(
	query: string,
	options: HybridSearchOptions = {},
): Promise<PolicySearchData> {
	const res = await api.post<{ code: number; data: PolicySearchData }>(
		"/api/v1/policies/search/hybrid",
		{
			query,
			category: options.category,
			limit: options.limit ?? 10,
			threshold: options.threshold ?? 0.1,
			similarity_weight: options.similarity_weight ?? 0.7,
			keyword_weight: options.keyword_weight ?? 0.3,
		},
	);
	return res.data;
}

export type SearchMode = "semantic" | "text" | "hybrid";
