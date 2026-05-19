class ContextSimulator:
    def simulate(self, participants, environment):
        env = environment or {}
        return {
            "mode": "dynamic_context",
            "participants": participants or [],
            "constraints": {
                "tone": env.get("tone", "neutral"),
                "clarity_required": float(env.get("clarity_required", 0.7)),
                "ambiguity_allowed": float(env.get("ambiguity_allowed", 0.3)),
            },
        }
