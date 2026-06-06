import re


_PLACEHOLDER_TRANSLATION = re.compile(r"^\[[a-z]{2,}(?:-[a-z0-9]+)?->[a-z]{2,}(?:-[a-z0-9]+)?\]", re.I)


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


def resolve_translation_text(cip_clarify: bool, cip: dict | None, fallback_text: str) -> str:
    """Keep Marian/NLLB output when CIP asks to clarify instead of blanking translation."""
    text = choose_translation(cip, fallback_text)
    if cip_clarify and not str(text or "").strip() and str(fallback_text or "").strip():
        return str(fallback_text).strip()
    return str(text or "").strip()


def is_cip_clarification(cip: dict | None) -> bool:
    decision = get_cip_decision(cip)
    return bool(decision and decision.get("type") == "clarification")


def should_block_translation_for_cip(
    cip: dict | None,
    fallback_text: str,
    translation_confidence: float | None = None,
) -> bool:
    if not is_cip_clarification(cip):
        return False

    fallback = (fallback_text or "").strip()
    if not fallback or _PLACEHOLDER_TRANSLATION.match(fallback):
        return True

    decision = get_cip_decision(cip) or {}
    reason = str(decision.get("reason") or "").lower()
    analysis = cip.get("analysis") if isinstance(cip, dict) else {}
    domains = analysis.get("domains") if isinstance(analysis, dict) else {}
    high_stakes = bool(isinstance(domains, dict) and (domains.get("high_stakes") or domains.get("risk_level") in {"high", "critical"}))
    if high_stakes or "high_stakes" in reason or "safety" in reason:
        return True

    if translation_confidence is None and isinstance(cip, dict):
        translation_confidence = cip.get("translation_confidence")
    try:
        confidence = float(translation_confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    return confidence < 0.4


def get_cip_confidence(cip: dict | None) -> float | None:
    if not isinstance(cip, dict) or cip.get("confidence") is None:
        return None
    try:
        return float(cip.get("confidence"))
    except (TypeError, ValueError):
        return None


def apply_cip_decision(response: dict, cip: dict | None, *, blocking: bool | None = None) -> dict:
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
            message = decision.get("message")
            if blocking is None:
                blocking = True
            if blocking:
                response["clarify"] = True
            else:
                response["cip_advisory"] = True
            if message and blocking:
                response["clarify_message"] = message
    return response
