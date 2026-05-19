class CommunicationGraph:
    def __init__(self):
        self.nodes = {}  # user_id -> node (future expansion)
        self.edges = {}  # (user_a, user_b) -> relationship data

    def _edge_key(self, user_a: str, user_b: str):
        return tuple(sorted([str(user_a), str(user_b)]))

    def add_interaction(self, user_a: str, user_b: str, data: dict):
        key = self._edge_key(user_a, user_b)
        if key not in self.edges:
            self.edges[key] = {
                "misunderstandings": 0,
                "successful_clarifications": 0,
                "total_interactions": 0,
                "dominant_confusion_topics": [],
            }
        edge = self.edges[key]
        edge["total_interactions"] += 1
        if data.get("misunderstanding"):
            edge["misunderstandings"] += 1
        if data.get("clarified"):
            edge["successful_clarifications"] += 1
        topic = data.get("topic")
        if topic:
            topics = edge.get("dominant_confusion_topics", [])
            topics.append(topic)
            edge["dominant_confusion_topics"] = topics[-10:]

    def snapshot(self) -> dict:
        return {"nodes": self.nodes, "edges": self.edges}
