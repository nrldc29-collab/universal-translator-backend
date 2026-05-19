class UserModel {
  constructor(userId) {
    this.userId = userId;
    this.profile = {
      clarityPreference: 0.7,
      ambiguityTolerance: 0.4,
      emotionalTone: "neutral",
    };
  }

  updateFromInteraction(interaction = {}) {
    if (interaction.confused) {
      this.profile.clarityPreference = Math.min(1, this.profile.clarityPreference + 0.05);
    }
    if (interaction.success) {
      this.profile.ambiguityTolerance = Math.min(1, this.profile.ambiguityTolerance + 0.02);
    }
  }
}

module.exports = { UserModel };
