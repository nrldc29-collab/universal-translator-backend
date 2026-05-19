class CivilizationRegistry:
    def __init__(self):
        self.civilizations = {}

    def create_civilization(self, civ_id: str):
        self.civilizations[civ_id] = {
            "norms": {},
            "clarity_score": 0.5,
            "ambiguity_tolerance": 0.5,
            "population": 0,
        }
        return civ_id

    def get(self, civ_id: str):
        return self.civilizations.get(civ_id)

    def update_population(self, civ_id: str, delta: int):
        if civ_id in self.civilizations:
            self.civilizations[civ_id]["population"] += int(delta)
