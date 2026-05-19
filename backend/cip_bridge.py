def get_cip_decision(cip: dict | None) -> dict | None:
    if isinstance(cip, dict) and isinstance(cip.get("decision"), dict):
        return cip["decision"]
    return None


def get_cip_translation(cip: dict | None) -> str | None:
    if not isinstance(cip, dict):
        return None
    decision = get_cip_decision(cip)
    if decision and decision.get("type") == "clarification":
        return None
    translated = cip.get("translated")
    if isinstance(translated, str) and translated.strip():
        return translated
    return None


def choose_translation(cip: dict | None, fallback_text: str) -> str:
    return get_cip_translation(cip) or fallback_text


def is_cip_clarification(cip: dict | None) -> bool:
    decision = get_cip_decision(cip)
    return bool(decision and decision.get("type") == "clarification")


def get_cip_confidence(cip: dict | None) -> float | None:
    if not isinstance(cip, dict) or cip.get("confidence") is None:
        return None
    try:
        return float(cip.get("confidence"))
    except (TypeError, ValueError):
        return None


def apply_cip_decision(response: dict, cip: dict | None) -> dict:
    decision = get_cip_decision(cip)
    translation = get_cip_translation(cip)
    if isinstance(cip, dict):
        response["translated_by"] = (cip.get("translation_source") or "CIP") if translation else "UT"
        if cip.get("provider"):
            response["cip_provider"] = cip.get("provider")
        if cip.get("confidence") is not None:
            response["cip_confidence"] = cip.get("confidence")
        if cip.get("analysis"):
            response["cip_analysis"] = cip.get("analysis")
        if cip.get("response_plan"):
            response["cip_response_plan"] = cip.get("response_plan")
    else:
        response["translated_by"] = "UT"
    if decision:
        response["cip_decision"] = decision
        if decision.get("type") == "clarification":
            response["clarify"] = True
            message = decision.get("message")
            if message:
                response["clarify_message"] = message
    return response
