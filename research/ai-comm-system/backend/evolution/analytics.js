class BehaviorAnalytics {
  analyze(logs) {
    if (!logs || logs.length === 0) {
      return { confusionRate: 0, successRate: 0, stabilityScore: 0 };
    }
    const confusionRate = logs.filter((l) => l.confusion).length / logs.length;
    const successRate = logs.filter((l) => l.success).length / logs.length;
    return {
      confusionRate,
      successRate,
      stabilityScore: successRate - confusionRate,
    };
  }
}

module.exports = { BehaviorAnalytics };
