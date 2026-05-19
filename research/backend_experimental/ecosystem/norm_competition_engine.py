class NormCompetitionEngine:
    def compete(self, civ_a: dict, civ_b: dict) -> dict:
        score_a = float(civ_a.get("clarity_score", 0.0)) - float(civ_a.get("ambiguity_tolerance", 0.0))
        score_b = float(civ_b.get("clarity_score", 0.0)) - float(civ_b.get("ambiguity_tolerance", 0.0))
        if score_a > score_b:
            return {"winner": "civilization_a", "adopted_norm": civ_a}
        return {"winner": "civilization_b", "adopted_norm": civ_b}
