"""
ForgeFlow AI - LangGraph Agent Graph Builder.

Constructs the StateGraph that orchestrates the after-sales ticket
processing pipeline:

    detect_intent → lookup_order → check_logistics
    → check_policy → make_decision → execute

With conditional routing after decision for human-in-the-loop and
escalation, and error handling from every node.

From PRD Section 7.2: LangGraph Node Implementation.
"""

import inspect

from langgraph.graph import END, StateGraph

from forgeflow.agent.nodes import (
    check_logistics_node,
    check_policy_node,
    detect_intent_node,
    execute_action_node,
    handle_error_node,
    lookup_order_node,
    make_decision_node,
)
from forgeflow.agent.state import AgentState
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="agent.graph")

# ── Pipeline order: maps each node to its successor (or None) ──
_FORWARD_MAP: dict[str, str | None] = {
    "detect_intent": "lookup_order",
    "lookup_order": "check_logistics",
    "check_logistics": "check_policy",
    "check_policy": "make_decision",
    "make_decision": None,  # Handled by conditional routing
    "execute": None,  # Ends pipeline
}


def _next_node_after(node_name: str) -> str:
    """Return the next node after *node_name*, or ``"end"``."""
    next_node = _FORWARD_MAP.get(node_name)
    if next_node:
        return next_node
    return "end"


def _wrap_with_error_handler(node_fn, node_name: str):
    """Wrap a primary node so exceptions are caught and routed to the error handler.

    When a node raises an exception, instead of propagating to the top-level
    try/except in AgentService, the wrapper catches it, sets ``error_message``
    and ``current_step`` on state, and returns.  The graph's conditional edges
    then route to ``handle_error`` for classification and recovery.
    """

    if inspect.iscoroutinefunction(node_fn):

        async def wrapped(state: AgentState) -> dict:
            try:
                return await node_fn(state)
            except Exception as exc:
                logger.error(
                    "agent_node_exception",
                    node=node_name,
                    ticket_id=state.get("ticket_id", "unknown"),
                    error=str(exc)[:300],
                )
                return {
                    "error_message": str(exc),
                    "current_step": node_name,
                }
    else:

        def wrapped(state: AgentState) -> dict:
            try:
                return node_fn(state)
            except Exception as exc:
                logger.error(
                    "agent_node_exception",
                    node=node_name,
                    ticket_id=state.get("ticket_id", "unknown"),
                    error=str(exc)[:300],
                )
                return {
                    "error_message": str(exc),
                    "current_step": node_name,
                }

    return wrapped


def build_agent_graph() -> StateGraph:
    """Build and compile the LangGraph agent state machine.

    Node flow:
        detect_intent → lookup_order → check_logistics → check_policy
        → make_decision → [conditional routing] → execute → END
                        ├── requires_approval → END (interrupt)
                        └── escalate/investigate → END

    Error handling:
        Every primary node is wrapped so that exceptions are caught and
        routed to handle_error_node, which may:
        - Retry the node (returns to same node)
        - Fallback and continue (proceeds to next node)
        - Escalate / terminate

    Returns:
        Compiled LangGraph StateGraph ready to invoke.
    """
    builder = StateGraph(AgentState)

    # =========================================================================
    # 1. Add all nodes (primary nodes are wrapped for error handling)
    # =========================================================================
    builder.add_node("detect_intent", _wrap_with_error_handler(detect_intent_node, "detect_intent"))
    builder.add_node("lookup_order", _wrap_with_error_handler(lookup_order_node, "lookup_order"))
    builder.add_node("check_logistics", _wrap_with_error_handler(check_logistics_node, "check_logistics"))
    builder.add_node("check_policy", _wrap_with_error_handler(check_policy_node, "check_policy"))
    builder.add_node("make_decision", _wrap_with_error_handler(make_decision_node, "make_decision"))
    builder.add_node("execute", _wrap_with_error_handler(execute_action_node, "execute"))
    builder.add_node("handle_error", handle_error_node)

    # =========================================================================
    # 2. Entry point
    # =========================================================================
    builder.set_entry_point("detect_intent")

    # =========================================================================
    # 3. Conditional routing after each primary node (error vs normal flow)
    # =========================================================================
    # Primary nodes in pipeline order
    primary_nodes = [
        "detect_intent",
        "lookup_order",
        "check_logistics",
        "check_policy",
        "make_decision",
        "execute",
    ]

    def route_after_node(state: AgentState, *, next_node: str) -> str:
        """Check for error after a primary node has run.

        If ``error_message`` is set, route to the error handler.
        Otherwise proceed to *next_node*.
        """
        if state.get("error_message"):
            return "handle_error"
        return next_node

    for _idx, node_name in enumerate(primary_nodes):
        next_node = _FORWARD_MAP.get(node_name)
        if next_node:
            # Make a closure that captures this node's successor
            def _route(state: AgentState, n=next_node) -> str:
                return route_after_node(state, next_node=n)

            builder.add_conditional_edges(
                node_name,
                _route,
                {"handle_error": "handle_error", next_node: next_node},
            )
        else:
            # Last nodes (make_decision, execute) — still need error routing
            if node_name == "make_decision":
                # make_decision already has its own conditional edges for
                # business routing.  We need a layered approach:
                #   1. First check for error → handle_error
                #   2. Otherwise use the normal business routing
                # Accomplish this by making make_decision ALWAYS route to a
                # "gate" that checks for errors before applying business logic.
                pass  # See step 4 below for the combined router
            else:
                # execute → on success go to END, on error go to handle_error
                def _execute_route(state: AgentState) -> str:
                    if state.get("error_message"):
                        return "handle_error"
                    return "end"

                builder.add_conditional_edges(
                    node_name,
                    _execute_route,
                    {"handle_error": "handle_error", "end": END},
                )

    # =========================================================================
    # 4. Combined routing after make_decision (error check + business logic)
    # =========================================================================
    def route_after_decision(state: AgentState) -> str:
        """Determine the next step after the decision node.

        Checks for errors first, then applies business routing logic.

        Returns:
            - "handle_error" if an exception was caught
            - "pending_approval" if human approval is needed
            - "execute" if action should be performed
            - "end" for escalation or investigation
        """
        # Error check takes priority
        if state.get("error_message"):
            return "handle_error"

        requires_approval = state.get("requires_approval", False)
        action = state.get("recommended_action")

        if requires_approval:
            return "pending_approval"

        if action in ("auto_refund", "auto_exchange", "send_notification"):
            return "execute"

        return "end"

    builder.add_conditional_edges(
        "make_decision",
        route_after_decision,
        {
            "handle_error": "handle_error",
            "pending_approval": END,  # Wait for human — will be resumed later
            "execute": "execute",
            "end": END,
        },
    )

    # =========================================================================
    # 5. Conditional routing after error handler (retry / continue / end)
    # =========================================================================
    def route_after_error(state: AgentState) -> str:
        """Determine where to go after error handling.

        The error handler sets current_step to one of:
        - The original node name → retry that node
        - "{node}_done" → continue to the next node
        - defaults → end (escalation / termination)
        """
        current_step = state.get("current_step", "")
        error = state.get("error_message")

        # Error was cleared and step set to "_done" → proceed to next node
        if current_step.endswith("_done") and not error:
            base_node = current_step.replace("_done", "")
            return _next_node_after(base_node)

        # Status indicates failure or escalation → end
        if state.get("status") in ("failed", "escalated"):
            return "end"

        # Otherwise: retry by routing back to the original node
        # (only if current_step matches a known primary node)
        if current_step in primary_nodes and not error:
            return current_step

        return "end"  # Safe default

    builder.add_conditional_edges(
        "handle_error",
        route_after_error,
        {
            **{name: name for name in primary_nodes},  # Retry: route back to any primary node
            **{_FORWARD_MAP[name]: _FORWARD_MAP[name] for name in primary_nodes if _FORWARD_MAP[name]},
            "end": END,
        },
    )

    return builder.compile()


# Module-level compiled graph (lazy-initialized by get_agent_graph())
_agent_graph: StateGraph | None = None


def get_agent_graph() -> StateGraph:
    """Return the compiled agent graph instance (lazy singleton).

    The graph is compiled on first call, not at import time, to avoid
    import-time side effects that break testing and CLI tools.

    Returns:
        Compiled LangGraph StateGraph.
    """
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph
