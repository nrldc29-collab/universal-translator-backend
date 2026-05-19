class ResponseSimulator:
    def simulate(self, text: str):
        t = (text or "").lower()
        interpretations = []
        if "fine" in t:
            interpretations.append("positive or passive-aggressive")
        if "whatever" in t:
            interpretations.append("dismissive or frustrated")
        if "?" in (text or ""):
            interpretations.append("questioning intent")
        return interpretations
