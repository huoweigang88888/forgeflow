"""
ForgeFlow AI — Locust Load Testing.

Performance testing to validate Phase 5 readiness.
Target: 50 concurrent tickets, P95 < 500ms for API, < 5s for Agent.

Usage:
    pip install locust
    locust -f docker/locust/locustfile.py --host=http://localhost:8000

Advanced:
    locust -f docker/locust/locustfile.py --host=http://localhost:8000 \\
        --users 100 --spawn-rate 10 --run-time 300s --headless \\
        --csv=reports/load-test
"""

import random
import string
import time
from typing import Any

from locust import HttpUser, between, task
from locust.exception import RescheduleTask


# ── Test Data Pool ──

SHOPIFY_DOMAINS = [
    "test.myshopify.com",
    "store-alpha.myshopify.com",
    "store-beta.myshopify.com",
    "boutique-demo.myshopify.com",
]

CUSTOMER_EMAILS = [
    "buyer_{i}@example.com",
    "vip_customer_{i}@example.com",
    "new_user_{i}@gmail.com",
]

ISSUE_TEMPLATES = {
    "shipping_delay": [
        "My order #{order} hasn't arrived yet. It's been {days} days.",
        "Where is my package #{order}? I ordered it {days} days ago!",
        "Order #{order} is delayed. Can you check what's going on?",
        "Still waiting for order #{order} after {days} days. This is unacceptable.",
    ],
    "refund_request": [
        "I want to return order #{order} and get a full refund.",
        "Please refund my order #{order}. The product didn't meet my expectations.",
        "Cancel order #{order} and refund me immediately.",
        "I changed my mind about order #{order}. I want my money back.",
    ],
    "damaged_item": [
        "Order #{order} arrived completely broken! I need a replacement ASAP!",
        "The item in order #{order} is damaged. Please help!",
        "Package #{order} was smashed when it arrived. I want a refund.",
        "Received a defective product for order #{order}. Very disappointed.",
    ],
    "wrong_item": [
        "You sent me the wrong item for order #{order}!",
        "Order #{order} is not what I ordered. I wanted a different size.",
        "Wrong color delivered for order #{order}. Please fix this.",
    ],
    "exchange": [
        "Can I exchange order #{order} for a different size?",
        "I need to swap order #{order} for another variant.",
        "Request exchange for order #{order}: size M → size L.",
    ],
    "other": [
        "When will you restock the blue one?",
        "Do you offer free shipping to Canada?",
        "How long does delivery usually take?",
        "What's your return policy for sale items?",
    ],
}

ORDER_IDS_POOL = [f"gid://shopify/Order/{random.randint(10000, 99999)}" for _ in range(200)]


# ── Helper Functions ──

def random_order_id() -> str:
    """Return a random order ID from the pool."""
    return random.choice(ORDER_IDS_POOL)


def random_tenant() -> str:
    """Return a random tenant domain."""
    return random.choice(SHOPIFY_DOMAINS)


def random_email() -> str:
    """Generate a realistic-looking email address."""
    template = random.choice(CUSTOMER_EMAILS)
    return template.format(i=random.randint(1, 9999))


def random_issue(issue_type: str | None = None) -> str:
    """Generate a realistic issue text from templates."""
    if issue_type is None:
        issue_type = random.choice(list(ISSUE_TEMPLATES.keys()))
    template = random.choice(ISSUE_TEMPLATES[issue_type])
    return template.format(
        order=str(random.randint(1000, 99999)),
        days=random.randint(3, 21),
    )


def random_ticket_id() -> str:
    """Generate a random ticket ID for polling."""
    chars = string.ascii_lowercase + string.digits
    suffix = "".join(random.choices(chars, k=12))
    return f"tkt_{suffix}"


# ── User Behavior Class ──

class ForgeFlowLoadTest(HttpUser):
    """Simulates realistic user load on the ForgeFlow API.

    User types simulated:
    - Customer support agents: browsing tickets, approving
    - System webhooks: creating new tickets (primary load)
    - Admins: viewing dashboards, managing policies

    Performance targets (Phase 5):
    - P95 API latency < 500ms
    - P95 Agent end-to-end < 5s
    - Error rate < 1%
    """

    wait_time = between(0.5, 3.0)  # Realistic user think time

    def on_start(self):
        """Initialize session with a random tenant."""
        self.tenant_id = random_tenant()
        self.headers = {
            "Authorization": "Bearer test-token",
            "X-Shopify-Domain": self.tenant_id,
            "Content-Type": "application/json",
        }
        self.request_times: dict[str, list[float]] = {}

    def _record_latency(self, name: str, response_time_ms: float):
        """Track per-endpoint response times for custom reporting."""
        if name not in self.request_times:
            self.request_times[name] = []
        self.request_times[name].append(response_time_ms)

    def _check_response(self, response, operation: str) -> bool:
        """Validate response and log failures.

        Returns True if the response is acceptable (2xx or 4xx for known cases).
        """
        if response.status_code in (200, 201):
            return True

        if response.status_code == 404:
            # 404 is expected for polling non-existent ticket IDs — not an error
            return True

        if response.status_code == 422:
            # Validation error — log but don't fail the test
            response.failure(f"{operation}: validation error (422) — {response.text[:200]}")
            return True

        if response.status_code >= 500:
            response.failure(f"{operation}: server error ({response.status_code})")
            return False

        # Unexpected status
        response.failure(f"{operation}: unexpected status ({response.status_code})")
        return False

    # ──────────────────────────────────────────────────────────────────
    # Ticket Creation (Primary Load — 70% of traffic)
    # ──────────────────────────────────────────────────────────────────

    @task(40)
    def create_ticket_shipping_delay(self):
        """Create a shipping delay ticket (most common case, ~40%)."""
        issue_text = random_issue("shipping_delay")
        order_id = random_order_id()

        with self.client.post(
            "/api/v1/tickets",
            json={
                "customer_email": random_email(),
                "issue_text": issue_text,
                "order_id": order_id,
            },
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/tickets (shipping_delay)",
        ) as response:
            self._check_response(response, "create_ticket_shipping_delay")
            if response.status_code == 201:
                self._record_latency("create_ticket", response.elapsed.total_seconds() * 1000)

    @task(20)
    def create_ticket_refund_request(self):
        """Create a refund request ticket (~20%)."""
        with self.client.post(
            "/api/v1/tickets",
            json={
                "customer_email": random_email(),
                "issue_text": random_issue("refund_request"),
                "order_id": random_order_id(),
            },
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/tickets (refund_request)",
        ) as response:
            self._check_response(response, "create_ticket_refund")

    @task(10)
    def create_ticket_damaged_item(self):
        """Create a damaged item ticket (~10%)."""
        with self.client.post(
            "/api/v1/tickets",
            json={
                "customer_email": random_email(),
                "issue_text": random_issue("damaged_item"),
                "order_id": random_order_id(),
            },
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/tickets (damaged_item)",
        ) as response:
            self._check_response(response, "create_ticket_damaged")

    @task(5)
    def create_ticket_wrong_item(self):
        """Create a wrong-item ticket (~5%)."""
        with self.client.post(
            "/api/v1/tickets",
            json={
                "customer_email": random_email(),
                "issue_text": random_issue("wrong_item"),
                "order_id": random_order_id(),
            },
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/tickets (wrong_item)",
        ) as response:
            self._check_response(response, "create_ticket_wrong")

    @task(3)
    def create_ticket_exchange(self):
        """Create an exchange request ticket (~3%)."""
        with self.client.post(
            "/api/v1/tickets",
            json={
                "customer_email": random_email(),
                "issue_text": random_issue("exchange"),
                "order_id": random_order_id(),
            },
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/tickets (exchange)",
        ) as response:
            self._check_response(response, "create_ticket_exchange")

    @task(2)
    def create_ticket_other(self):
        """Create a non-standard inquiry (~2%)."""
        with self.client.post(
            "/api/v1/tickets",
            json={
                "customer_email": random_email(),
                "issue_text": random_issue("other"),
                "order_id": None,
            },
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/tickets (other)",
        ) as response:
            self._check_response(response, "create_ticket_other")

    # ──────────────────────────────────────────────────────────────────
    # Ticket Browsing & Management (Secondary Load — 15% of traffic)
    # ──────────────────────────────────────────────────────────────────

    @task(8)
    def list_tickets(self):
        """Browse ticket list with pagination."""
        page = random.randint(1, 3)
        status = random.choice(["pending", "processing", "pending_approval", "all"])

        with self.client.get(
            f"/api/v1/tickets",
            params={"status": status, "page": page, "limit": 20},
            headers=self.headers,
            catch_response=True,
            name="GET /api/v1/tickets",
        ) as response:
            self._check_response(response, "list_tickets")

    @task(4)
    def get_ticket_detail(self):
        """View a specific ticket's detail page."""
        ticket_id = random_ticket_id()
        with self.client.get(
            f"/api/v1/tickets/{ticket_id}",
            headers=self.headers,
            catch_response=True,
            name="GET /api/v1/tickets/:id",
        ) as response:
            # 404 is expected for random IDs
            if response.status_code not in (200, 404):
                response.failure(f"get_ticket_detail: unexpected status {response.status_code}")

    @task(3)
    def get_ticket_status(self):
        """Poll ticket status (REST fallback for WebSocket)."""
        ticket_id = random_ticket_id()
        with self.client.get(
            f"/api/v1/tickets/{ticket_id}/status",
            headers=self.headers,
            catch_response=True,
            name="GET /api/v1/tickets/:id/status",
        ) as response:
            if response.status_code not in (200, 404):
                response.failure(f"get_ticket_status: unexpected status {response.status_code}")

    # ──────────────────────────────────────────────────────────────────
    # Dashboard & Reports (5% of traffic)
    # ──────────────────────────────────────────────────────────────────

    @task(3)
    def dashboard_stats(self):
        """Load dashboard metrics."""
        with self.client.get(
            "/api/v1/dashboard/stats",
            headers=self.headers,
            catch_response=True,
            name="GET /api/v1/dashboard/stats",
        ) as response:
            self._check_response(response, "dashboard_stats")

    # ──────────────────────────────────────────────────────────────────
    # Policy Management (Admin — 5% of traffic)
    # ──────────────────────────────────────────────────────────────────

    @task(3)
    def list_policies(self):
        """List knowledge base policies."""
        with self.client.get(
            "/api/v1/policies",
            headers=self.headers,
            catch_response=True,
            name="GET /api/v1/policies",
        ) as response:
            self._check_response(response, "list_policies")

    @task(2)
    def search_policies(self):
        """Search knowledge base semantically."""
        queries = [
            "refund policy for damaged items",
            "shipping delay compensation",
            "exchange size policy",
            "return window",
            "VIP customer handling",
        ]
        with self.client.post(
            "/api/v1/policies/search",
            json={"query": random.choice(queries), "limit": 5},
            headers=self.headers,
            catch_response=True,
            name="POST /api/v1/policies/search",
        ) as response:
            self._check_response(response, "search_policies")

    # ──────────────────────────────────────────────────────────────────
    # Health Check (1% of traffic)
    # ──────────────────────────────────────────────────────────────────

    @task(1)
    def health_check(self):
        """Health endpoint — should always respond quickly."""
        with self.client.get(
            "/api/health",
            catch_response=True,
            name="GET /api/health",
        ) as response:
            if response.status_code != 200:
                response.failure(f"health_check: status {response.status_code}")
            elif response.elapsed.total_seconds() > 1.0:
                response.failure(
                    f"health_check: slow response ({response.elapsed.total_seconds():.2f}s)"
                )
