"""
ForgeFlow AI - Agent Service (Orchestration Layer).

The AgentService is the main entry point for running after-sales tickets
through the LangGraph agent pipeline.

Responsibilities:
1. Accept ticket input and create AgentState
2. Run the LangGraph graph with provider injection
3. Handle human-in-the-loop interruptions (approval flow)
4. Persist state updates to the database
5. Publish real-time status via Redis Pub/Sub

Usage:
    service = AgentService(db_session)
    ticket_id = await service.run(ticket_input)
"""

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from forgeflow.agent.graph import get_agent_graph
from forgeflow.agent.state import get_initial_state
from forgeflow.core.config import get_settings
from forgeflow.core.exceptions import AgentError, ProviderError
from forgeflow.monitoring.logger import get_logger
from forgeflow.providers.registry import ProviderRegistry

logger = get_logger(component="agent.service")


class AgentService:
    """Orchestrates the end-to-end agent workflow for a single ticket.

    Usage:
        service = AgentService()
        ticket_id = await service.run(
            ticket_id="tkt_xxx",
            platform="mock",
            shopify_domain="test.myshopify.com",
            customer_email="buyer@test.com",
            issue_text="Where is my order?",
            order_id="order_123",
        )
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        """Initialize the agent service.

        Args:
            redis_client: Optional Redis client for pub/sub status updates.
        """
        self.redis = redis_client
        self.graph = get_agent_graph()
        self.settings = get_settings()

    async def run(
        self,
        ticket_id: str,
        platform: str,
        shopify_domain: str,
        customer_email: str,
        issue_text: str,
        order_id: str | None = None,
        customer_name: str | None = None,
        attachments: list[str] | None = None,
        mock_overrides: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Run the agent pipeline for a new ticket.

        Creates initial state and executes the LangGraph graph until
        completion or human-in-the-loop interruption.

        Args:
            ticket_id: UUID of the ticket.
            platform: Platform identifier (mock, shopify, etc.).
            shopify_domain: Tenant domain.
            customer_email: Customer's email.
            issue_text: The customer's message.
            order_id: Optional platform order ID.
            customer_name: Optional customer name.
            attachments: Optional attachment URLs.
            mock_overrides: Optional provider overrides for testing.
            access_token: Optional Shopify OAuth access token for real API calls.

        Returns:
            Final AgentState as a dict.

        Raises:
            AgentError: If the graph execution fails unexpectedly.
            ProviderError: If the platform is not registered.
        """
        # Validate platform
        if not ProviderRegistry.is_registered(platform):
            raise ProviderError(
                provider=platform,
                message=f"Unknown platform '{platform}'. Register it first.",
                retryable=False,
            )

        # Build initial state
        initial_state = get_initial_state(
            ticket_id=ticket_id,
            platform=platform,
            shopify_domain=shopify_domain,
            customer_email=customer_email,
            issue_text=issue_text,
            order_id=order_id,
            customer_name=customer_name,
            attachments=attachments,
            mock_overrides=mock_overrides,
            access_token=access_token,
        )

        logger.info(
            "agent_run_start",
            ticket_id=ticket_id,
            platform=platform,
            intent_hint=issue_text[:80],
        )

        start_time = time.perf_counter()

        try:
            # Execute the graph
            final_state = await self.graph.ainvoke(initial_state)

            processing_duration_ms = int((time.perf_counter() - start_time) * 1000)
            final_state["processing_duration_ms"] = processing_duration_ms
            final_state["completed_at"] = datetime.now(UTC)

            # Determine final status
            if final_state.get("requires_approval"):
                final_state["status"] = "pending_approval"
                final_state["sla_deadline"] = datetime.now(UTC) + timedelta(hours=24)
            elif final_state.get("execution_status") == "success":
                final_state["status"] = "resolved"
            elif final_state.get("recommended_action") == "escalate_to_human":
                final_state["status"] = "escalated"
            elif final_state.get("execution_status") == "failed":
                final_state["status"] = "failed"
            else:
                final_state["status"] = "resolved"

            # Publish final status
            await self._publish_status(ticket_id, final_state)

            logger.info(
                "agent_run_complete",
                ticket_id=ticket_id,
                status=final_state.get("status"),
                action=final_state.get("recommended_action"),
                duration_ms=processing_duration_ms,
            )

            return dict(final_state)

        except Exception as e:
            processing_duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(
                "agent_run_failed",
                ticket_id=ticket_id,
                error=str(e)[:300],
                duration_ms=processing_duration_ms,
            )
            raise AgentError(
                node=initial_state.get("current_step", "unknown"),
                message=str(e),
            ) from e

    async def resume(
        self,
        ticket_id: str,
        state: dict[str, Any],
        approved: bool,
        approver_note: str = "",
    ) -> dict[str, Any]:
        """Resume a ticket that was paused for human approval.

        Args:
            ticket_id: The ticket to resume.
            state: The current AgentState (as stored from the interrupt point).
            approved: True if the human approved the action.
            approver_note: Optional note from the approver.

        Returns:
            Final state after execution.

        Raises:
            AgentError: If the ticket is not in a resumable state.
        """
        status = state.get("status")
        if status != "pending_approval":
            raise AgentError(
                node="resume",
                message=f"Cannot resume ticket in status '{status}'. Expected 'pending_approval'.",
            )

        if approved:
            # Human approved — clear the approval flag and continue to execute
            state["requires_approval"] = False
            state["current_step"] = "execute"
            state["status"] = "processing"
            state["sla_deadline"] = None
            logger.info(
                "agent_resume_approved",
                ticket_id=ticket_id,
                note=approver_note[:100],
            )
        else:
            # Human rejected — escalate instead
            state["recommended_action"] = "escalate_to_human"
            state["requires_approval"] = False
            state["approval_reason"] = f"Rejected by approver: {approver_note}"
            state["status"] = "escalated"
            state["sla_deadline"] = None
            logger.info(
                "agent_resume_rejected",
                ticket_id=ticket_id,
                note=approver_note[:100],
            )

        start_time = time.perf_counter()

        try:
            final_state = await self.graph.ainvoke(state)

            processing_duration_ms = int((time.perf_counter() - start_time) * 1000)
            final_state["processing_duration_ms"] = processing_duration_ms
            final_state["completed_at"] = datetime.now(UTC)

            if final_state.get("execution_status") == "success":
                final_state["status"] = "resolved"
            elif final_state.get("status") == "escalated":
                pass  # Already set
            else:
                final_state["status"] = "resolved"

            await self._publish_status(ticket_id, final_state)

            return dict(final_state)

        except Exception as e:
            raise AgentError(
                node="resume_execute",
                message=str(e),
            ) from e

    async def _publish_status(self, ticket_id: str, state: dict[str, Any]) -> None:
        """Publish a status update to Redis Pub/Sub for WebSocket delivery.

        Args:
            ticket_id: The ticket whose status changed.
            state: Current agent state.
        """
        if self.redis is None:
            return

        try:
            message = {
                "type": _determine_event_type(state),
                "ticket_id": ticket_id,
                "step": state.get("current_step", "unknown"),
                "status": state.get("status", "processing"),
                "timestamp": datetime.now(UTC).isoformat(),
                "data": _build_event_data(state),
            }
            await self.redis.publish(
                f"ticket:{ticket_id}",
                json.dumps(message),
            )
        except Exception as e:
            logger.warning(
                "agent_publish_failed",
                ticket_id=ticket_id,
                error=str(e)[:200],
            )


def _determine_event_type(state: dict[str, Any]) -> str:
    """Determine the WebSocket event type from the current state."""
    if state.get("requires_approval"):
        return "pending_approval"
    if state.get("status") == "resolved":
        return "completed"
    if state.get("status") == "failed":
        return "error"
    if state.get("error_message"):
        return "error"
    if state.get("execution_status") == "success":
        return "execution_result"
    return "step_update"


def _build_event_data(state: dict[str, Any]) -> dict[str, Any]:
    """Build the data payload for a WebSocket status event."""
    return {
        "intent": state.get("intent"),
        "confidence": state.get("confidence"),
        "recommended_action": state.get("recommended_action"),
        "refund_amount": state.get("refund_amount"),
        "requires_approval": state.get("requires_approval"),
        "decision_explanation": state.get("decision_explanation"),
        "execution_status": state.get("execution_status"),
        "execution_result": state.get("execution_result"),
        "customer_response": state.get("customer_response"),
        "error_message": state.get("error_message"),
        "processing_duration_ms": state.get("processing_duration_ms"),
    }
