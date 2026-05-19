const { OutcomeTracker } = require("./outcome_tracker");
const { BehaviorAnalytics } = require("./analytics");
const { RuleEvolutionEngine } = require("./rule_engine");
const { PolicyCompiler } = require("./policy_compiler");

class SelfImprovingSystem {
  constructor() {
    this.tracker = new OutcomeTracker();
    this.analytics = new BehaviorAnalytics();
    this.evolver = new RuleEvolutionEngine();
    this.compiler = new PolicyCompiler();

    this.rules = {
      ambiguityThreshold: 0.5,
      forceClarification: false,
      responseSpeedBoost: false,
    };
  }

  recordOutcome(event) {
    this.tracker.record(event);
  }

  evolveSystem() {
    const logs = this.tracker.getRecent(200);
    const metrics = this.analytics.analyze(logs);
    this.rules = this.evolver.evolve(metrics, this.rules);
    return this.compiler.compile(this.rules);
  }
}

module.exports = { SelfImprovingSystem };
