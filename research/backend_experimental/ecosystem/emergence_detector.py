class EmergenceDetector:
    def detect(self, communication_data: dict):
        clarity_trend = communication_data.get("clarity_trend", []) or []
        if len(clarity_trend) < 5:
            return None
        if sum(clarity_trend[-5:]) / 5 > 0.8:
            return {"emergence_detected": True, "type": "high_clarity_protocol", "confidence": 0.9}
        return {"emergence_detected": False}
