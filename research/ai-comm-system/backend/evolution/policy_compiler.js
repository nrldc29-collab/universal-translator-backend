class PolicyCompiler {
  compile(rules) {
    return {
      shouldClarify: !!rules.forceClarification,
      ambiguityLimit: Number(rules.ambiguityThreshold || 0.5),
      speedMode: !!rules.responseSpeedBoost,
      allowShort: !!rules.allowShortResponses,
    };
  }
}

module.exports = { PolicyCompiler };
