"""Platform adapters — readiness heuristics per runtime (Node/Next first)."""

from app.adapters.node_next import NodeNextReadiness, assess_node_next

__all__ = ["NodeNextReadiness", "assess_node_next"]
