const { negotiate } = require("./negotiation_network");
const { SelectionEngine } = require("./selection_engine");
const { GlobalMetrics } = require("./global_metrics");

class CommunicationCivilization {
  constructor(species = []) {
    this.species = species;
    this.selector = new SelectionEngine();
    this.metrics = new GlobalMetrics();
  }

  step(task = {}) {
    if (this.species.length < 2) {
      return { best_species: this.species[0]?.name || null, winner: null, global_clarity: this.metrics.compute(this.species).global_clarity_index };
    }
    const sorted = this.selector.select(this.species);
    const best = sorted[0];
    const rival = sorted[1];
    const result = negotiate(best, rival, task);
    best.evolve({ clarity: 0.1 });
    const global = this.metrics.compute(this.species);
    return { best_species: best.name, winner: result.winner, global_clarity: global.global_clarity_index };
  }
}

module.exports = { CommunicationCivilization };
