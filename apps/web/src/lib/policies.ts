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
