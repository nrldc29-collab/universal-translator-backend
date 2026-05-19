class SemanticEvolutionEngine:
    def evolve(self, language_state: dict) -> dict:
        evolution = {}
        for word, usage in (language_state or {}).items():
            confusion = float((usage or {}).get("confusion", 0.0))
            efficiency = float((usage or {}).get("efficiency", 0.0))
            if confusion > 0.6:
                evolution[word] = "replace_with_clearer_term"
            if efficiency > 0.8:
                evolution[word] = "compress_or_abbreviate"
        return evolution
