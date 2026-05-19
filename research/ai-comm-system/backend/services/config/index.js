let config = {
  ambiguityThreshold: 0.5,
  confidenceThreshold: 0.45,
  responseSpeedBoost: false,
  responseMode: 'normal',
};

function updateConfig(patch) {
  config = { ...config, ...patch };
}

function getConfig() {
  return config;
}

module.exports = { updateConfig, getConfig };
