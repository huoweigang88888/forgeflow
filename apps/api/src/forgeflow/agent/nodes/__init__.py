"""
ForgeFlow AI - Agent Nodes Package.

Each node is a standalone async function that:
1. Takes AgentState as input
2. Returns a partial dict update
3. Raises exceptions on failure (caught by LangGraph error routing)
"""

from forgeflow.agent.nodes.decision import make_decision_node
from forgeflow.agent.nodes.error_handler import handle_error_node
from forgeflow.agent.nodes.execute import execute_action_node
from forgeflow.agent.nodes.intent import detect_intent_node
from forgeflow.agent.nodes.logistics import check_logistics_node
from forgeflow.agent.nodes.order_lookup import lookup_order_node
from forgeflow.agent.nodes.policy import check_policy_node

__all__ = [
    "check_logistics_node",
    "check_policy_node",
    "detect_intent_node",
    "execute_action_node",
    "handle_error_node",
    "lookup_order_node",
    "make_decision_node",
]
