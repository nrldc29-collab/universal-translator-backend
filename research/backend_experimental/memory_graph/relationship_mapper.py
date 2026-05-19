class RelationshipMapper:
    def map(self, edge: dict | None) -> str:
        if not edge:
            return "no_data"
        total = max(1, int(edge.get("total_interactions", 0)))
        misunderstandings = int(edge.get("misunderstandings", 0))
        conflict_rate = misunderstandings / total
        if conflict_rate > 0.6:
            return "high_frustration_risk"
        if conflict_rate > 0.3:
            return "unstable_communication"
        if int(edge.get("successful_clarifications", 0)) > misunderstandings:
            return "improving_understanding"
        return "stable"
