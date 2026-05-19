class LatencyEngine:
    def __init__(self):
        self.avg_stt = 0.0
        self.avg_translate = 0.0
        self.avg_tts = 0.0

    def update(self, stt: float | int = 0.0, translate: float | int = 0.0, tts: float | int = 0.0):
        # EWMA smoothing
        self.avg_stt = (self.avg_stt * 0.8) + (float(stt) * 0.2)
        self.avg_translate = (self.avg_translate * 0.8) + (float(translate) * 0.2)
        self.avg_tts = (self.avg_tts * 0.8) + (float(tts) * 0.2)

    def total(self) -> float:
        return float(self.avg_stt + self.avg_translate + self.avg_tts)
