class RealityCompiler:
    def compile(self, meaning: dict, context: dict):
        constraints = (context or {}).get("constraints", {})
        clarity_required = float(constraints.get("clarity_required", 0.7))
        social_weight = float(meaning.get("social_weight", 0.4))
        certainty = float(meaning.get("certainty", 0.5))
        if certainty < clarity_required:
            return {"output": "Clarification required before proceeding.", "mode": "halt_and_refine"}
        if social_weight > 0.7:
            return {"output": "Softened socially-aware response generated.", "mode": "empathy_adjusted"}
        return {"output": "Direct communication allowed.", "mode": "standard"}
