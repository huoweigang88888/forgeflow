/**
 * Zustand — Client-side UI State Store.
 *
 * Phase 2: Dashboard filter state, approval queue selection, ticket filters.
 */

import type { TicketStatus } from "@/types";
import { create } from "zustand";

// ── UI State ──

interface UIState {
	sidebarOpen: boolean;
	toggleSidebar: () => void;
	setSidebarOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
	sidebarOpen: true,
	toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
	setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));

// ── Ticket Filter State ──

interface TicketFilterState {
	status: TicketStatus | "all";
	platform: string | "all";
	page: number;
	pageSize: number;
	setStatus: (status: TicketStatus | "all") => void;
	setPlatform: (platform: string | "all") => void;
	setPage: (page: number) => void;
	setPageSize: (size: number) => void;
	resetFilters: () => void;
}

export const useTicketFilterStore = create<TicketFilterState>((set) => ({
	status: "all",
	platform: "all",
	page: 1,
	pageSize: 20,
	setStatus: (status) => set({ status, page: 1 }),
	setPlatform: (platform) => set({ platform, page: 1 }),
	setPage: (page) => set({ page }),
	setPageSize: (pageSize) => set({ pageSize, page: 1 }),
	resetFilters: () => set({ status: "all", platform: "all", page: 1, pageSize: 20 }),
}));

// ── Approval Queue State ──

interface ApprovalState {
	selectedTicketId: string | null;
	isSubmitting: boolean;
	selectTicket: (ticketId: string | null) => void;
	setSubmitting: (submitting: boolean) => void;
}

export const useApprovalStore = create<ApprovalState>((set) => ({
	selectedTicketId: null,
	isSubmitting: false,
	selectTicket: (ticketId) => set({ selectedTicketId: ticketId }),
	setSubmitting: (isSubmitting) => set({ isSubmitting }),
}));

// ── Knowledge Base State ──

interface KnowledgeBaseState {
	searchQuery: string;
	selectedCategory: string | null;
	isUploadOpen: boolean;
	page: number;
	setSearchQuery: (query: string) => void;
	setSelectedCategory: (category: string | null) => void;
	setUploadOpen: (open: boolean) => void;
	setPage: (page: number) => void;
}

export const useKnowledgeBaseStore = create<KnowledgeBaseState>((set) => ({
	searchQuery: "",
	selectedCategory: null,
	isUploadOpen: false,
	page: 1,
	setSearchQuery: (searchQuery) => set({ searchQuery }),
	setSelectedCategory: (selectedCategory) => set({ selectedCategory, page: 1 }),
	setUploadOpen: (isUploadOpen) => set({ isUploadOpen }),
	setPage: (page) => set({ page }),
}));
