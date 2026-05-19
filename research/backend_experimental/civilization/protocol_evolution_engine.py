class ProtocolEvolutionEngine:
    def __init__(self):
        self.protocols = {
            "clarity_standard": 0.5,
            "ambiguity_tolerance": 0.5,
        }

    def update(self, feedback_data: dict):
        if float(feedback_data.get("misunderstanding_rate", 0.0)) > 0.6:
            self.protocols["ambiguity_tolerance"] = max(0.0, self.protocols["ambiguity_tolerance"] - 0.1)
            self.protocols["clarity_standard"] = min(1.0, self.protocols["clarity_standard"] + 0.1)
        if float(feedback_data.get("communication_efficiency", 0.0)) > 0.8:
            self.protocols["ambiguity_tolerance"] = min(1.0, self.protocols["ambiguity_tolerance"] + 0.05)
        return dict(self.protocols)
