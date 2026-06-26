"""
ForgeFlow AI - Agent Runtime Package.

The LangGraph-based agent state machine that processes after-sales tickets:
- state.py: AgentState TypedDict definition and initial state factory
- graph.py: LangGraph StateGraph construction
- service.py: AgentService orchestration layer
- retry_config.py: Per-node retry policies and error classification
- prompts.py: LLM prompt templates for all agent nodes
- nodes/: Individual agent nodes (intent, order, logistics, policy, decision, execute)

Architecture:
    AgentService.run() → graph.ainvoke(initial_state)
        → detect_intent → lookup_order → check_logistics
        → check_policy → make_decision → execute → END

Import performance: LangGraph (agent.graph) is the single heaviest import
in the project.  To keep ``import forgeflow.agent`` fast, we only expose
lightweight symbols (AgentState, get_initial_state) at module level.
Import ``AgentService`` or node functions directly from their submodules
when needed:

    from forgeflow.agent.service import AgentService   # triggers full chain
    from forgeflow.agent.graph import get_agent_graph  # triggers full chain
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from forgeflow.agent.state import AgentState, get_initial_state

if TYPE_CHECKING:
    from forgeflow.agent.graph import get_agent_graph
    from forgeflow.agent.nodes import (
        check_logistics_node,
        check_policy_node,
        detect_intent_node,
        execute_action_node,
        handle_error_node,
        lookup_order_node,
        make_decision_node,
    )
    from forgeflow.agent.service import AgentService

__all__ = [
    "AgentService",
    "AgentState",
    "check_logistics_node",
    "check_policy_node",
    "detect_intent_node",
    "execute_action_node",
    "get_agent_graph",
    "get_initial_state",
    "handle_error_node",
    "lookup_order_node",
    "make_decision_node",
]


def __getattr__(name: str):
    """Lazy import for heavyweight symbols.

    Only ``AgentState`` and ``get_initial_state`` are loaded at import
    time.  Everything else (AgentService, graph, nodes) is imported on
    first access — which typically happens during ``create_app()`` or
    inside a request handler, not at module-load time.
    """
    if name == "AgentService":
        from forgeflow.agent.service import AgentService as _s

        return _s
    if name == "get_agent_graph":
        from forgeflow.agent.graph import get_agent_graph as _g

        return _g
    if name in _NODE_MAP:
        mod_name, attr = _NODE_MAP[name]
        import importlib

        mod = importlib.import_module(mod_name)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_NODE_MAP: dict[str, tuple[str, str]] = {
    "detect_intent_node": ("forgeflow.agent.nodes.intent", "detect_intent_node"),
    "lookup_order_node": ("forgeflow.agent.nodes.order_lookup", "lookup_order_node"),
    "check_logistics_node": ("forgeflow.agent.nodes.logistics", "check_logistics_node"),
    "check_policy_node": ("forgeflow.agent.nodes.policy", "check_policy_node"),
    "make_decision_node": ("forgeflow.agent.nodes.decision", "make_decision_node"),
    "execute_action_node": ("forgeflow.agent.nodes.execute", "execute_action_node"),
    "handle_error_node": ("forgeflow.agent.nodes.error_handler", "handle_error_node"),
}
