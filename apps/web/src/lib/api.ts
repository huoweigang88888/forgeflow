/**
 * ForgeFlow API Client.
 *
 * Thin wrapper around fetch() with JWT auth, JSON handling, and error mapping.
 */

import { useAuthStore } from "./auth-store";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface APIError {
	code: string;
	message: string;
	details?: Record<string, unknown>;
}

export class ForgeFlowAPIError extends Error {
	code: string;
	status: number;
	details?: Record<string, unknown>;

	constructor(status: number, error: APIError) {
		super(error.message);
		this.name = "ForgeFlowAPIError";
		this.code = error.code;
		this.status = status;
		this.details = error.details;
	}
}

async function request<T>(
	endpoint: string,
	options: RequestInit = {},
): Promise<T> {
	const url = `${API_BASE_URL}${endpoint}`;

	const headers: Record<string, string> = {
		"Content-Type": "application/json",
		"X-Request-ID": crypto.randomUUID(),
		...options.headers as Record<string, string>,
	};

	// Inject JWT from auth store (set by Shopify OAuth flow)
	const token = useAuthStore.getState().token;
	if (token) {
		headers["Authorization"] = `Bearer ${token}`;
	}

	const response = await fetch(url, {
		...options,
		headers,
	});

	if (!response.ok) {
		let error: APIError;
		try {
			error = await response.json();
		} catch {
			error = { code: "NETWORK_ERROR", message: response.statusText };
		}
		throw new ForgeFlowAPIError(response.status, error);
	}

	// Handle 204 No Content
	if (response.status === 204) {
		return undefined as T;
	}

	return response.json();
}

export const api = {
	get: <T>(endpoint: string) => request<T>(endpoint),
	post: <T>(endpoint: string, data?: unknown) =>
		request<T>(endpoint, {
			method: "POST",
			body: data ? JSON.stringify(data) : undefined,
		}),
	put: <T>(endpoint: string, data?: unknown) =>
		request<T>(endpoint, {
			method: "PUT",
			body: data ? JSON.stringify(data) : undefined,
		}),
	patch: <T>(endpoint: string, data?: unknown) =>
		request<T>(endpoint, {
			method: "PATCH",
			body: data ? JSON.stringify(data) : undefined,
		}),
	delete: <T>(endpoint: string) => request<T>(endpoint, { method: "DELETE" }),
};
