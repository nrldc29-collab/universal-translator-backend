class CulturalProfileEngine:
    def __init__(self):
        self.profiles = {}

    def update(self, user_id: str, region: str | None, behavior: dict):
        if user_id not in self.profiles:
            self.profiles[user_id] = {
                "region": region or "unknown",
                "directness": 0.5,
                "politeness_preference": 0.5,
                "ambiguity_tolerance": 0.5,
            }
        profile = self.profiles[user_id]
        if behavior.get("frequent_clarifications"):
            profile["ambiguity_tolerance"] = max(0.0, profile["ambiguity_tolerance"] - 0.1)
        if behavior.get("uses_idioms"):
            profile["ambiguity_tolerance"] = min(1.0, profile["ambiguity_tolerance"] + 0.1)
        if (region or "").lower() in ["japan", "korea"]:
            profile["politeness_preference"] = min(1.0, profile["politeness_preference"] + 0.2)
        return profile
