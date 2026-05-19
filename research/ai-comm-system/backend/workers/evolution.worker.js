const { getMetrics } = require("../services/analytics");
const { updateConfig } = require("../services/config");

async function evolveSystem() {
  const metrics = await getMetrics();
  if (metrics.confusionRate > 0.4) {
    updateConfig({ ambiguityThreshold: 0.45 });
  }
  if (metrics.successRate > 0.8) {
    updateConfig({ responseSpeedBoost: true });
  }
  console.log("Evolution cycle complete:", metrics);
}

setInterval(evolveSystem, 1000 * 60 * 10);
