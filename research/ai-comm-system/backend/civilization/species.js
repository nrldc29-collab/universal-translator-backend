class CommunicationSpecies {
  constructor(name, ruleset) {
    this.name = name;
    this.ruleset = ruleset || {};
    this.performance = {
      clarity: 0.5,
      speed: 0.5,
      misunderstanding: 0.5,
    };
  }

  evolve(delta = {}) {
    this.performance.clarity += delta.clarity || 0;
    this.performance.speed += delta.speed || 0;
    this.performance.misunderstanding += delta.misunderstanding || 0;
    // clamp for stability
    this.performance.clarity = Math.max(0, Math.min(1, this.performance.clarity));
    this.performance.speed = Math.max(0, Math.min(1, this.performance.speed));
    this.performance.misunderstanding = Math.max(0, Math.min(1, this.performance.misunderstanding));
  }
}

module.exports = { CommunicationSpecies };
