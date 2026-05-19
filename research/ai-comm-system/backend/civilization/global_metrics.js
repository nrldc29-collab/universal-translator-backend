class GlobalMetrics {
  compute(speciesList = []) {
    if (!speciesList.length) return { global_clarity_index: 0 };
    const total = speciesList.reduce((sum, s) => sum + Number(s.performance.clarity || 0), 0);
    return { global_clarity_index: total / speciesList.length };
  }
}

module.exports = { GlobalMetrics };
