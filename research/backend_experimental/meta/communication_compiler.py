class CommunicationCompiler:
    def compile(self, intent: str, protocol: dict) -> dict:
        if (protocol or {}).get("new_protocol") == "explicit_confirmation_required":
            return {"compiled_message": f"{intent}? Please confirm meaning before proceeding."}
        if (protocol or {}).get("new_protocol") == "compressed_expression_mode":
            return {"compiled_message": self._compress(intent)}
        return {"compiled_message": intent}

    def _compress(self, text: str) -> str:
        return "".join([w[:2] for w in (text or "").split()])
