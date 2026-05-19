class ProtocolGenerator:
    def generate(self, communication_patterns: dict) -> dict:
        patterns = communication_patterns or {}
        if float(patterns.get("misunderstanding_rate", 0.0)) > 0.5:
            return {
                "new_protocol": "explicit_confirmation_required",
                "rule": "All ambiguous statements must be clarified before response",
            }
        if float(patterns.get("efficiency", 0.0)) > 0.8:
            return {
                "new_protocol": "compressed_expression_mode",
                "rule": "Shortened expressions preferred for high-speed contexts",
            }
        return {"new_protocol": "stable", "rule": "no change"}
