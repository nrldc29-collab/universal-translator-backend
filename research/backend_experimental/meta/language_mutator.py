class LanguageMutator:
    def mutate(self, text: str, evolution_rules: dict) -> str:
        t = text or ""
        for word, rule in (evolution_rules or {}).items():
            if rule == "replace_with_clearer_term":
                t = t.replace(word, f"[clarified:{word}]")
            if rule == "compress_or_abbreviate":
                t = t.replace(word, word[:3])
        return t
