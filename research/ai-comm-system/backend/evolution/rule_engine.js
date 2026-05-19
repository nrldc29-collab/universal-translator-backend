class RuleEvolutionEngine {
  evolve(metrics, currentRules) {
    const updated = { ...currentRules };
    if (metrics.confusionRate > 0.4) {
      updated.ambiguityThreshold = Math.max(0, (updated.ambiguityThreshold || 0.5) - 0.1);
      updated.forceClarification = true;
    }
    if (metrics.successRate > 0.8) {
      updated.responseSpeedBoost = true;
    }
    if (metrics.stabilityScore > 0.7) {
      updated.allowShortResponses = true;
    }
    return updated;
  }
}

module.exports = { RuleEvolutionEngine };
