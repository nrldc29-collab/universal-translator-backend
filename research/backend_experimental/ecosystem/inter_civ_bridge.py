class InterCivilizationBridge:
    def translate_norms(self, civ_a: dict, civ_b: dict, message: str) -> str:
        adapted = message
        if float(civ_a.get("clarity_score", 0.0)) > float(civ_b.get("clarity_score", 0.0)):
            adapted = "simplified version: " + message
        if float(civ_b.get("ambiguity_tolerance", 0.0)) > 0.7:
            adapted = message + " (context preserved)"
        return adapted
