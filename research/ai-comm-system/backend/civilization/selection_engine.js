class SelectionEngine {
  select(speciesList = []) {
    return [...speciesList].sort((a, b) => {
      const scoreA = a.performance.clarity - a.performance.misunderstanding;
      const scoreB = b.performance.clarity - b.performance.misunderstanding;
      return scoreB - scoreA;
    });
  }
}

module.exports = { SelectionEngine };
