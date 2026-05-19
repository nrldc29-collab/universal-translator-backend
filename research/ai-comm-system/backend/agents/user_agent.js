class UserAgent {
  constructor(userId) {
    this.userId = userId;
    this.memory = [];
    this.styleProfile = {
      directness: 0.5,
      clarityPreference: 0.7,
      emotionalTone: "neutral",
    };
  }

  updateMemory(interaction) {
    this.memory.push(interaction);
    if (interaction && interaction.confused) {
      this.styleProfile.clarityPreference = Math.min(1, this.styleProfile.clarityPreference + 0.05);
    }
  }

  generateContext() {
    return {
      recentMemory: this.memory.slice(-10),
      style: this.styleProfile,
    };
  }
}

module.exports = { UserAgent };
