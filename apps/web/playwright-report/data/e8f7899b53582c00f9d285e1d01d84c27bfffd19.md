# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ticket-approval-flow.spec.ts >> Ticket Approval Flow >> Frontend: approvals page loads
- Location: e2e\ticket-approval-flow.spec.ts:317:6

# Error details

```
TimeoutError: page.goto: Timeout 15000ms exceeded.
Call log:
  - navigating to "http://localhost:3000/approvals", waiting until "domcontentloaded"

```

# Test source

```ts
  218 | 			// Reject the ticket
  219 | 			const rejectRes = await request.post(
  220 | 				`${API_BASE}/api/v1/tickets/${ticketId}/reject`,
  221 | 				{
  222 | 					data: {
  223 | 						approved: false,
  224 | 						note: "Too risky, escalate to human",
  225 | 						approver_id: "e2e-tester",
  226 | 					},
  227 | 				},
  228 | 			);
  229 | 			expect([200, 500]).toContain(rejectRes.status());
  230 | 			if (rejectRes.status() === 200) {
  231 | 				const rejectBody = await rejectRes.json();
  232 | 				expect(rejectBody.data.status).toBe("escalated");
  233 | 			}
  234 | 		} else {
  235 | 			// Agent completed without needing approval
  236 | 			expect(["resolved", "escalated", "failed"]).toContain(
  237 | 				terminal.status,
  238 | 			);
  239 | 		}
  240 | 	});
  241 | 
  242 | 	// Test 5: REST poll fallback — poll /status until terminal
  243 | 	test("REST poll: /status returns progress until terminal state", async ({
  244 | 		request,
  245 | 	}) => {
  246 | 		const createRes = await request.post(`${API_BASE}/api/v1/tickets`, {
  247 | 			data: {
  248 | 				customer_email: "buyer@example.com",
  249 | 				issue_text:
  250 | 					"Where is my order #1111? It's been delayed for 3 weeks.",
  251 | 				customer_name: "Bob Wilson",
  252 | 				platform: "mock",
  253 | 				order_id: "order_1111",
  254 | 			},
  255 | 		});
  256 | 		expect(createRes.status()).toBe(201);
  257 | 		const { data } = await createRes.json();
  258 | 		const ticketId = data.ticket_id;
  259 | 
  260 | 		// Poll up to 30 seconds for a terminal state
  261 | 		const terminal = await pollUntilTerminal(request, ticketId, 30_000);
  262 | 
  263 | 		// order_1111 → $11.11 < $50 threshold → auto-refund without approval → resolved
  264 | 		expect(["resolved", "escalated", "failed", "pending_approval"]).toContain(
  265 | 			terminal.status,
  266 | 		);
  267 | 	});
  268 | 
  269 | 	// Test 6: Ticket detail API returns correct shape
  270 | 	test("GET /api/v1/tickets/:id returns full ticket detail", async ({
  271 | 		request,
  272 | 	}) => {
  273 | 		const createRes = await request.post(`${API_BASE}/api/v1/tickets`, {
  274 | 			data: {
  275 | 				customer_email: "buyer@example.com",
  276 | 				issue_text: "Test ticket for detail API",
  277 | 				customer_name: "Test User",
  278 | 				platform: "mock",
  279 | 			},
  280 | 		});
  281 | 		expect(createRes.status()).toBe(201);
  282 | 		const { data: createData } = await createRes.json();
  283 | 
  284 | 		const detailRes = await request.get(
  285 | 			`${API_BASE}/api/v1/tickets/${createData.ticket_id}`,
  286 | 		);
  287 | 		expect(detailRes.status()).toBe(200);
  288 | 		const body = await detailRes.json();
  289 | 
  290 | 		expect(body.code).toBe(0);
  291 | 		expect(body.data.ticket).toBeDefined();
  292 | 		const ticket = body.data.ticket;
  293 | 		expect(ticket.ticket_id).toBe(createData.ticket_id);
  294 | 		expect(ticket.status).toBeDefined();
  295 | 		expect(ticket.platform).toBe("mock");
  296 | 		expect(ticket.customer_email).toBe("buyer@example.com");
  297 | 		expect(ticket.issue_text).toBeDefined();
  298 | 		expect(ticket.created_at).toBeDefined();
  299 | 	});
  300 | 
  301 | 	// Test 7: Ticket detail page loads in the browser
  302 | 	test("Frontend: ticket detail page renders", async ({ page, request }) => {
  303 | 		const { data } = await createTicket(request);
  304 | 
  305 | 		await page.goto(`/tickets/${data.ticket_id}`, {
  306 | 			waitUntil: "domcontentloaded",
  307 | 			timeout: 15_000,
  308 | 		});
  309 | 
  310 | 		// Should show the ticket detail page
  311 | 		await expect(
  312 | 			page.getByRole("heading", { level: 1 }),
  313 | 		).toBeVisible({ timeout: 10_000 });
  314 | 	});
  315 | 
  316 | 	// Test 8: Approvals page loads and shows pending items
  317 | 	test("Frontend: approvals page loads", async ({ page }) => {
> 318 | 		await page.goto("/approvals", {
      |              ^ TimeoutError: page.goto: Timeout 15000ms exceeded.
  319 | 			waitUntil: "domcontentloaded",
  320 | 			timeout: 15_000,
  321 | 		});
  322 | 
  323 | 		// Page should load without error — check for approval-related content
  324 | 		const heading = page.getByRole("heading", { level: 1 });
  325 | 		await expect(heading).toBeVisible({ timeout: 10_000 });
  326 | 		const headingText = await heading.textContent();
  327 | 		// Heading should contain "approval" (case-insensitive)
  328 | 		expect(headingText?.toLowerCase()).toContain("approval");
  329 | 	});
  330 | });
  331 | 
```