"""Governance module for NAIA cognitive runtime kernel."""

from governance.approval_queue import ApprovalQueue, ApprovalRequest, ApprovalStatus
from governance.decision_log import DecisionLog, DecisionRecord

__all__ = [
    "ApprovalQueue",
    "ApprovalRequest",
    "ApprovalStatus",
    "DecisionLog",
    "DecisionRecord",
    "governance_hook",
]


def __getattr__(name: str):
    if name == "governance_hook":
        from governance.governance_hook import governance_hook

        return governance_hook
    raise AttributeError(name)
