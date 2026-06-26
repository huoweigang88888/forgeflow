/**
 * ForgeFlow — Shared TypeScript type definitions.
 *
 * Mirrors the backend AgentState + API response shapes.
 */

// ── Ticket ──

export type TicketIntent =
	| "shipping_delay"
	| "refund_request"
	| "wrong_item"
	| "damaged_item"
	| "exchange_request"
	| "partial_refund"
	| "subscription_cancel"
	| "pre_sale_inquiry"
	| "other";

export type TicketStatus =
	| "received"
	| "processing"
	| "pending_approval"
	| "resolved"
	| "escalated"
	| "failed";

export type TicketAction =
	| "auto_refund"
	| "auto_exchange"
	| "investigate"
	| "escalate_to_human"
	| "send_notification";

export type ExecutionStatus =
	| "pending"
	| "running"
	| "success"
	| "failed"
	| "pending_manual";

export type StepName =
	| "detect_intent"
	| "lookup_order"
	| "check_logistics"
	| "check_policy"
	| "make_decision"
	| "execute";

export type StepStatus = "done" | "pending" | "failed" | "skipped";

// ── API Response Wrappers ──

export interface APIResponse<T> {
	code: number;
	message?: string;
	data: T;
}

export interface PaginatedData<T> {
	tickets: T[];
	total: number;
	page: number;
	page_size: number;
}

// ── Ticket Detail ──

export interface TicketStep {
	step: StepName;
	status: StepStatus;
	result: string | null;
}

export interface PendingApproval {
	action: TicketAction;
	amount: number | null;
	reason: string;
	decision_explanation: string;
	deadline: string | null;
	sla_remaining_seconds: number | null;
	sla_breached: boolean;
}

export interface TicketDetail {
	ticket_id: string;
	platform: string;
	shopify_domain: string;
	customer_email: string;
	customer_name: string | null;
	order_id: string | null;
	issue_text: string;
	issue_language: string | null;
	attachments: string[];
	intent: TicketIntent | null;
	confidence: number | null;
	urgency: string | null;
	sentiment: string | null;
	order_info: Record<string, unknown> | null;
	logistics_status: Record<string, unknown> | null;
	relevant_policies: Record<string, unknown>[] | null;
	recommended_action: TicketAction | null;
	refund_amount: number | null;
	refund_reason: string | null;
	requires_approval: boolean;
	approval_reason: string | null;
	decision_explanation: string | null;
	execution_status: ExecutionStatus | null;
	execution_result: Record<string, unknown> | null;
	status: TicketStatus;
	current_step: string | null;
	error_message: string | null;
	retry_count: number;
	processing_duration_ms: number | null;
	completed_at: string | null;
	created_at: string;
	updated_at?: string;
}

// ── Ticket List Item (summary) ──

export interface TicketListItem {
	ticket_id: string;
	platform: string;
	customer_email: string;
	customer_name: string | null;
	issue_text: string;
	issue_language: string | null;
	intent: TicketIntent | null;
	status: TicketStatus;
	recommended_action: TicketAction | null;
	refund_amount: number | null;
	requires_approval: boolean;
	created_at: string;
	sla_deadline: string | null;
}

// ── Ticket Status (REST poll) ──

export interface TicketStatusInfo {
	ticket_id: string;
	status: TicketStatus;
	progress: number;
	steps: TicketStep[];
	pending_approval: PendingApproval | null;
}

// ── Dashboard Stats ──

export interface DashboardStats {
	total_tickets: number;
	resolved: number;
	escalated: number;
	pending_approval: number;
	failed: number;
	avg_processing_time_ms: number;
	auto_resolution_rate: number;
}

// ── Create Ticket ──

export interface TicketCreateInput {
	customer_email: string;
	issue_text: string;
	order_id?: string;
	customer_name?: string;
	attachments?: string[];
	platform?: string;
}

export interface TicketCreateResult {
	ticket_id: string;
	status: TicketStatus;
	estimated_completion?: string;
	ws_endpoint?: string;
	status_url?: string;
}

// ── Approval ──

export interface ApprovalInput {
	approved: boolean;
	note?: string;
	approver_id?: string;
}

export interface ApprovalResult {
	ticket_id: string;
	status: TicketStatus;
	execution_id: string | null;
}

// ── WebSocket Events ──

export type WSEventType =
	| "connected"
	| "step_update"
	| "pending_approval"
	| "completed"
	| "execution_result"
	| "error";

export interface WSEvent {
	type: WSEventType;
	ticket_id: string;
	step?: string;
	status?: TicketStatus;
	timestamp: string;
	data: {
		intent?: TicketIntent;
		confidence?: number;
		recommended_action?: TicketAction;
		refund_amount?: number;
		requires_approval?: boolean;
		decision_explanation?: string;
		execution_status?: ExecutionStatus;
		execution_result?: Record<string, unknown>;
		customer_response?: string;
		error_message?: string;
		processing_duration_ms?: number;
		message?: string;
	};
}

// ── Pagination ──

export interface PaginatedResponse<T> {
	items: T[];
	total: number;
	page: number;
	page_size: number;
	total_pages: number;
}

// ── API ──

export interface APIErrorResponse {
	code: string;
	message: string;
	details?: Record<string, unknown>;
	request_id?: string;
}

// ── Policy Documents ──

export interface PolicyDocument {
	id: string;
	title: string;
	content: string;
	content_hash: string;
	chunk_index: number;
	source_document_id: string | null;
	category: string | null;
	tags: string[];
	is_active: boolean;
	version: number;
	uploaded_by: string | null;
	uploaded_at: string | null;
	created_at: string | null;
	updated_at: string | null;
}

export interface PolicySearchHit {
	policy: PolicyDocument;
	similarity: number;
}

export interface PolicyCreateInput {
	title: string;
	content: string;
	category?: string;
	tags?: string[];
	shopify_domain?: string;
	platform?: string;
}

export interface PolicyUpdateInput {
	title?: string;
	content?: string;
	category?: string;
	tags?: string[];
	is_active?: boolean;
}

export interface PolicyListData {
	policies: PolicyDocument[];
	total: number;
	page: number;
	page_size: number;
}

export interface PolicySearchData {
	hits: PolicySearchHit[];
	query: string;
	total: number;
}

// ── Ticket Metrics (Monitoring Dashboard) ──

export interface ProcessingRatePoint {
	hour: string;
	count: number;
}

export interface LLMCostPoint {
	date: string;
	cost: number;
}

export interface LLMCostWeeklyPoint {
	week_start: string;
	cost: number;
}

export interface TrendPoint {
	date: string;
	rate: number;
	total: number;
	resolved: number;
}

export interface TicketMetrics {
	processing_rate: ProcessingRatePoint[];
	llm_cost_daily: LLMCostPoint[];
	llm_cost_weekly: LLMCostWeeklyPoint[];
	auto_resolve_trend: TrendPoint[];
	sla_compliance_rate: number;
	period_days: number;
}

// ── Auth / Shopify OAuth ──

export interface ShopifyAuthResponse {
	access_token: string; // ForgeFlow JWT
	shop_domain: string;
	scopes: string;
	installed_at: string;
}

export interface SessionInfo {
	authenticated: boolean;
	shop_domain: string | null;
	installed_at: string | null;
	scopes: string[];
}
