from stt_server.audit import write_audit_event
from stt_server.regional_routing import RegionalRoutingDecision


async def audit_regional_routing_decision(
    db,
    *,
    decision: RegionalRoutingDecision,
    actor_id: str | None,
) -> None:
    await write_audit_event(
        db,
        tenant_id=decision.tenant_id,
        actor_id=actor_id,
        event_type=(
            "tenant.regional_route_allowed"
            if decision.allowed
            else "tenant.regional_route_blocked"
        ),
        resource="regional_routing",
        payload={
            "home_region": decision.home_region,
            "request_region": decision.request_region,
            "allowed": decision.allowed,
            "reason": decision.reason,
        },
    )
