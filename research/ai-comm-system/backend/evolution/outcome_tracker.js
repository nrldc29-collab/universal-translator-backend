class OutcomeTracker {
  constructor() {
    this.logs = [];
  }

  record(event) {
    this.logs.push({
      timestamp: Date.now(),
      success: !!event.success,
      confusion: !!event.confusion,
      correction_needed: !!event.correction_needed,
      context: event.context || {},
    });
  }

  getRecent(n = 100) {
    return this.logs.slice(-n);
  }
}

module.exports = { OutcomeTracker };
