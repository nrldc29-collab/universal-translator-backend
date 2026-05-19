const logs = [];

function recordEvent(event) {
  logs.push({
    ts: Date.now(),
    confused: !!event.confused,
    success: !!event.success,
    latency: Number(event.latency || 0),
  });
}

function computeMetrics(sample = logs) {
  if (!sample.length) return { confusionRate: 0, successRate: 0, avgLatency: 0 };
  const confusionRate = sample.filter((l) => l.confused).length / sample.length;
  const successRate = sample.filter((l) => l.success).length / sample.length;
  const avgLatency = sample.reduce((a, b) => a + (b.latency || 0), 0) / sample.length;
  return { confusionRate, successRate, avgLatency };
}

async function getMetrics() {
  // In a real system, pull from Redis/DB aggregations.
  return computeMetrics(logs.slice(-1000));
}

module.exports = { recordEvent, computeMetrics, getMetrics };
