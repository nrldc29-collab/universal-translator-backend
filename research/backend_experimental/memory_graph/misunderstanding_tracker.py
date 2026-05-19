class MisunderstandingTracker:
    def __init__(self, graph):
        self.graph = graph

    def record(self, user_a: str, user_b: str, topic: str):
        key = tuple(sorted([user_a, user_b]))
        edge = self.graph.edges.get(key, None)
        if not edge:
            self.graph.add_interaction(user_a, user_b, {"topic": topic})
            edge = self.graph.edges.get(key, {})
        topics = edge.get("dominant_confusion_topics", [])
        topics.append(topic)
        edge["dominant_confusion_topics"] = topics[-10:]

    def get_conflict_score(self, user_a: str, user_b: str) -> float:
        key = tuple(sorted([user_a, user_b]))
        edge = self.graph.edges.get(key)
        if not edge:
            return 0.0
        if edge.get("total_interactions", 0) == 0:
            return 0.0
        return float(edge.get("misunderstandings", 0)) / float(edge.get("total_interactions", 1))
