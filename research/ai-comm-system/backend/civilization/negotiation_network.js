function negotiate(speciesA, speciesB, task) {
  const scoreA = speciesA.performance.clarity - speciesA.performance.misunderstanding;
  const scoreB = speciesB.performance.clarity - speciesB.performance.misunderstanding;
  if (scoreA > scoreB) {
    return { winner: speciesA.name, strategy: speciesA.ruleset };
  }
  return { winner: speciesB.name, strategy: speciesB.ruleset };
}

module.exports = { negotiate };
