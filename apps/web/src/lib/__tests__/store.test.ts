import {
	useApprovalStore,
	useKnowledgeBaseStore,
	useTicketFilterStore,
	useUIStore,
} from "@/lib/store";
/**
 * Tests for Zustand stores (src/lib/store.ts).
 */
import { describe, expect, it } from "vitest";

describe("useUIStore", () => {
	it("initializes with sidebar open", () => {
		expect(useUIStore.getState().sidebarOpen).toBe(true);
	});

	it("toggleSidebar flips the value", () => {
		useUIStore.setState({ sidebarOpen: true });
		useUIStore.getState().toggleSidebar();
		expect(useUIStore.getState().sidebarOpen).toBe(false);

		useUIStore.getState().toggleSidebar();
		expect(useUIStore.getState().sidebarOpen).toBe(true);
	});

	it("setSidebarOpen sets the sidebar state explicitly", () => {
		useUIStore.getState().setSidebarOpen(false);
		expect(useUIStore.getState().sidebarOpen).toBe(false);

		useUIStore.getState().setSidebarOpen(true);
		expect(useUIStore.getState().sidebarOpen).toBe(true);
	});
});

describe("useTicketFilterStore", () => {
	it("initializes with defaults", () => {
		const s = useTicketFilterStore.getState();
		expect(s.status).toBe("all");
		expect(s.platform).toBe("all");
		expect(s.page).toBe(1);
		expect(s.pageSize).toBe(20);
	});

	it("setStatus updates status and resets page to 1", () => {
		useTicketFilterStore.setState({ page: 5, status: "all" });
		useTicketFilterStore.getState().setStatus("pending_approval");
		const s = useTicketFilterStore.getState();
		expect(s.status).toBe("pending_approval");
		expect(s.page).toBe(1); // page resets
	});

	it("setPlatform updates platform and resets page to 1", () => {
		useTicketFilterStore.setState({ page: 5, platform: "all" });
		useTicketFilterStore.getState().setPlatform("woocommerce");
		const s = useTicketFilterStore.getState();
		expect(s.platform).toBe("woocommerce");
		expect(s.page).toBe(1); // page resets
	});

	it("setPage updates only the page", () => {
		useTicketFilterStore.setState({ status: "all" });
		useTicketFilterStore.getState().setPage(3);
		const s = useTicketFilterStore.getState();
		expect(s.page).toBe(3);
		expect(s.status).toBe("all"); // unchanged
	});

	it("setPageSize updates size and resets page", () => {
		useTicketFilterStore.setState({ page: 5, pageSize: 20 });
		useTicketFilterStore.getState().setPageSize(50);
		const s = useTicketFilterStore.getState();
		expect(s.pageSize).toBe(50);
		expect(s.page).toBe(1); // page resets
	});

	it("resetFilters restores defaults", () => {
		useTicketFilterStore.setState({
			status: "resolved",
			platform: "shopify",
			page: 4,
			pageSize: 50,
		});
		useTicketFilterStore.getState().resetFilters();
		const s = useTicketFilterStore.getState();
		expect(s.status).toBe("all");
		expect(s.platform).toBe("all");
		expect(s.page).toBe(1);
		expect(s.pageSize).toBe(20);
	});
});

describe("useApprovalStore", () => {
	it("initializes with no selection and not submitting", () => {
		const s = useApprovalStore.getState();
		expect(s.selectedTicketId).toBeNull();
		expect(s.isSubmitting).toBe(false);
	});

	it("selectTicket sets the ticket ID", () => {
		useApprovalStore.getState().selectTicket("ticket-123");
		expect(useApprovalStore.getState().selectedTicketId).toBe("ticket-123");

		useApprovalStore.getState().selectTicket(null);
		expect(useApprovalStore.getState().selectedTicketId).toBeNull();
	});

	it("setSubmitting toggles submission state", () => {
		useApprovalStore.getState().setSubmitting(true);
		expect(useApprovalStore.getState().isSubmitting).toBe(true);

		useApprovalStore.getState().setSubmitting(false);
		expect(useApprovalStore.getState().isSubmitting).toBe(false);
	});
});

describe("useKnowledgeBaseStore", () => {
	it("initializes with defaults", () => {
		const s = useKnowledgeBaseStore.getState();
		expect(s.searchQuery).toBe("");
		expect(s.selectedCategory).toBeNull();
		expect(s.isUploadOpen).toBe(false);
		expect(s.page).toBe(1);
	});

	it("setSearchQuery updates query", () => {
		useKnowledgeBaseStore.getState().setSearchQuery("refund policy");
		expect(useKnowledgeBaseStore.getState().searchQuery).toBe("refund policy");
	});

	it("setSelectedCategory updates category and resets page", () => {
		useKnowledgeBaseStore.setState({ page: 3 });
		useKnowledgeBaseStore.getState().setSelectedCategory("shipping");
		const s = useKnowledgeBaseStore.getState();
		expect(s.selectedCategory).toBe("shipping");
		expect(s.page).toBe(1);
	});

	it("setUploadOpen toggles upload modal", () => {
		useKnowledgeBaseStore.getState().setUploadOpen(true);
		expect(useKnowledgeBaseStore.getState().isUploadOpen).toBe(true);
	});

	it("setPage updates the page number", () => {
		useKnowledgeBaseStore.getState().setPage(4);
		expect(useKnowledgeBaseStore.getState().page).toBe(4);
	});
});
