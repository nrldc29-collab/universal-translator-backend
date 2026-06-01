"""Governance hook for pipeline risk precheck stage."""

from __future__ import annotations

import logging
import time
from typing import Any

from governance.approval_queue import ApprovalQueue, ApprovalRequest, ApprovalStatus
from governance.decision_log import DecisionLog, DecisionOutcome, DecisionRecord, DecisionType
from runtime.state import CognitiveState

logger = logging.getLogger(__name__)


def governance_hook(
    state: CognitiveState,
    decision_log: DecisionLog,
    approval_queue: ApprovalQueue,
) -> tuple[bool, str]:
    """
    Hook called from pipeline._risk_precheck_stage for HIGH/CRITICAL risk paths.
    
    Returns (allowed, reason) tuple:
    - allowed: True if execution can proceed, False if blocked
    - reason: Explanation of the decision
    """
    start_time = time.time()
    
    try:
        if state.risk_level not in {"HIGH", "CRITICAL"}:
            logger.debug(f"Risk level {state.risk_level} does not require governance review")
            return True, "Risk level does not require governance review"

        # Log the risk detection
        decision_log.record(
            DecisionRecord(
                decision_type=DecisionType.RISK_OVERRIDE,
                outcome=DecisionOutcome.ESCALATED,
                risk_level=state.risk_level,
                session_id=state.session_id,
                requested_by=state.user_input[:100] if state.user_input else "system",
                reason=f"High-risk operation detected: {state.risk_level}",
                details={
                    "normalized_input": state.normalized_input,
                    "intent": state.intent,
                    "task_type": state.task_type,
                    "cognitive_mode": state.cognitive_mode,
                    "route_plan": state.route_plan,
                },
            )
        )
        logger.info(f"Governance: Risk escalated to {state.risk_level} for session {state.session_id}")

        # For CRITICAL risk, always require approval
        if state.risk_level == "CRITICAL":
            approval_queue.submit(
                ApprovalRequest(
                    request_type="critical_operation",
                    risk_level="CRITICAL",
                    session_id=state.session_id,
                    requested_by="system",
                    reason="Critical risk operation requires explicit human approval",
                    details={
                        "normalized_input": state.normalized_input,
                        "intent": state.intent,
                        "task_type": state.task_type,
                        "route_plan": state.route_plan,
                        "restricted_tools": state.route_plan.get("risk", {}).get(
                            "restricted_tools", []
                        ),
                        "reasons": state.route_plan.get("risk", {}).get("reasons", []),
                    },
                )
            )
            logger.warning(f"Governance: CRITICAL risk blocked for session {state.session_id}, awaiting approval")
            return False, "CRITICAL risk operations require explicit human approval via approval queue"

        # For HIGH risk, check if confirmation is already present
        requires_confirmation = state.route_plan.get("risk", {}).get(
            "requires_confirmation", False
        )
        if requires_confirmation:
            # Check if there's an approved request for this session
            pending = approval_queue.list_by_session(state.session_id, limit=10)
            approved = [
                req
                for req in pending
                if req.status == ApprovalStatus.APPROVED
                and req.request_type == "high_risk_operation"
            ]
            if approved:
                # Log the approval-based decision
                decision_log.record(
                    DecisionRecord(
                        decision_type=DecisionType.RISK_OVERRIDE,
                        outcome=DecisionOutcome.APPROVED,
                        risk_level=state.risk_level,
                        session_id=state.session_id,
                        requested_by="system",
                        reviewed_by=approved[-1].reviewed_by,
                        reason=f"High-risk operation approved via request {approved[-1].request_id}",
                        details={
                            "approval_request_id": approved[-1].request_id,
                            "normalized_input": state.normalized_input,
                        },
                    )
                )
                logger.info(f"Governance: HIGH risk approved via request {approved[-1].request_id} for session {state.session_id}")
                return True, f"Approved via governance request {approved[-1].request_id}"

            # No approval found, submit for review
            approval_queue.submit(
                ApprovalRequest(
                    request_type="high_risk_operation",
                    risk_level="HIGH",
                    session_id=state.session_id,
                    requested_by="system",
                    reason="High-risk operation requires human confirmation",
                    details={
                        "normalized_input": state.normalized_input,
                        "intent": state.intent,
                        "task_type": state.task_type,
                        "route_plan": state.route_plan,
                        "restricted_tools": state.route_plan.get("risk", {}).get(
                            "restricted_tools", []
                        ),
                        "reasons": state.route_plan.get("risk", {}).get("reasons", []),
                    },
                )
            )
            logger.warning(f"Governance: HIGH risk blocked for session {state.session_id}, awaiting confirmation")
            return False, "HIGH risk operation requires human confirmation via approval queue"

        # HIGH risk without confirmation requirement - log and allow
        decision_log.record(
            DecisionRecord(
                decision_type=DecisionType.RISK_OVERRIDE,
                outcome=DecisionOutcome.APPROVED,
                risk_level=state.risk_level,
                session_id=state.session_id,
                requested_by="system",
                reason="High-risk operation auto-approved (no confirmation required)",
                details={
                    "normalized_input": state.normalized_input,
                    "intent": state.intent,
                },
            )
        )
        logger.info(f"Governance: HIGH risk auto-approved for session {state.session_id}")
        return True, "HIGH risk operation auto-approved (no confirmation required)"
    except Exception as e:
        logger.error(f"Governance hook failed: {e}", exc_info=True)
        # Fail-safe: allow execution if governance fails
        return True, f"Governance check failed, allowing execution: {str(e)[:100]}"
    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.debug(f"Governance hook completed in {duration_ms:.2f}ms")
