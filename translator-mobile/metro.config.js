const os = require("os");
const path = require("path");
const { getDefaultConfig } = require("expo/metro-config");
const { FileStore } = require("metro-cache");

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Store Metro cache outside OneDrive to avoid sync-related bundler stalls on Windows.
const cacheRoot = path.join(os.tmpdir(), "anai-translator-metro-cache");
config.cacheStores = [new FileStore({ root: path.join(cacheRoot, "metro") })];

// Keep worker count low so Metro bundling stays stable on Windows/OneDrive setups.
config.maxWorkers = 1;
config.projectRoot = __dirname;
config.watchFolders = [__dirname];
config.resolver.nodeModulesPaths = [path.resolve(__dirname, "node_modules")];
config.watcher = {
  ...config.watcher,
  healthCheck: {
    enabled: true,
    interval: 30000,
    timeout: 10000,
  },
};

module.exports = config;
