const { getDefaultConfig } = require("expo/metro-config");

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Keep worker count low so Metro bundling stays stable on Windows/OneDrive setups.
config.maxWorkers = 1;

module.exports = config;
