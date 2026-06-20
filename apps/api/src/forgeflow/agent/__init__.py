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
"""

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
from forgeflow.agent.state import AgentState, get_initial_state

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
