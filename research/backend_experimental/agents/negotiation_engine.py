class NegotiationEngine:
    def negotiate(self, agent_a_output: dict, agent_b_output: dict) -> dict:
        confidence_a = float(agent_a_output.get("confidence", 0.0))
        confidence_b = float(agent_b_output.get("confidence", 0.0))
        if confidence_a > confidence_b + 0.2:
            return agent_a_output
        if confidence_b > confidence_a + 0.2:
            return agent_b_output
        return {
            "type": "merged_intent",
            "message": "Clarified hybrid meaning",
            "confidence": (confidence_a + confidence_b) / 2.0,
        }
