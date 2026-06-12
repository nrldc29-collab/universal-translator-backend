const os = require("os");
const path = require("path");
const { getDefaultConfig } = require("expo/metro-config");
const { FileStore } = require("metro-cache");

const MOBILE_BUILD_ID = process.env.ANAI_MOBILE_BUILD_ID || "2026-06-11-fix152";
const MIN_FULL_BUNDLE_BYTES = 2_000_000;
const STUB_RETRY_MESSAGE =
  "Anai Metro full bundle not ready. Wait until the PC terminal shows ~1280 modules bundled, then retry.";
let lastFullBundleAt = 0;
let lastFullBundleBytes = 0;
let blockedStubCount = 0;

function isIncrementalBundleRequest(url) {
  const query = String(url || "");
  return /(?:^|[?&])modulesOnly=true/i.test(query)
    || /(?:^|[?&])shallow=true/i.test(query)
    || /deltaBundleId=/i.test(query);
}

function isBundleRequest(pathname) {
  return pathname.includes(".bundle") || pathname.includes("/index.bundle");
}

function bufferFullBundleResponse(req, res) {
  const chunks = [];
  const origWrite = res.write.bind(res);
  const origEnd = res.end.bind(res);
  const origWriteHead = res.writeHead.bind(res);
  let finished = false;
  let deferredStatusCode = 200;
  const deferredHeaders = {};

  res.writeHead = function writeHeadBuffered(statusCode, statusMessage, headers) {
    if (finished) {
      return origWriteHead(statusCode, statusMessage, headers);
    }
    if (typeof statusCode === "object") {
      headers = statusCode;
      statusCode = 200;
      statusMessage = undefined;
    }
    if (typeof statusMessage === "object") {
      headers = statusMessage;
      statusMessage = undefined;
    }
    deferredStatusCode = Number(statusCode) || 200;
    if (headers && typeof headers === "object") {
      Object.assign(deferredHeaders, headers);
    }
    return res;
  };

  res.write = function writeBuffered(chunk, encoding, cb) {
    if (chunk) {
      chunks.push(
        Buffer.isBuffer(chunk)
          ? chunk
          : Buffer.from(String(chunk), typeof encoding === "string" ? encoding : "utf8"),
      );
    }
    if (typeof encoding === "function") {
      cb = encoding;
    }
    if (cb) {
      process.nextTick(cb);
    }
    return true;
  };

  res.end = function endBuffered(chunk, encoding, cb) {
    if (finished) {
      return origEnd(chunk, encoding, cb);
    }
    finished = true;
    if (chunk) {
      chunks.push(
        Buffer.isBuffer(chunk)
          ? chunk
          : Buffer.from(String(chunk), typeof encoding === "string" ? encoding : "utf8"),
      );
    }
    const body = chunks.length ? Buffer.concat(chunks) : Buffer.alloc(0);
    if (body.length < MIN_FULL_BUNDLE_BYTES) {
      lastFullBundleAt = 0;
      lastFullBundleBytes = 0;
      blockedStubCount += 1;
      console.warn(`[anai] Blocked stub bundle #${blockedStubCount} (${body.length} bytes) for ${req.url}`);
      if (!res.headersSent) {
        origWriteHead(503, {
          "Content-Type": "text/plain; charset=utf-8",
          "Cache-Control": "no-store, no-cache, must-revalidate",
          "Content-Length": String(Buffer.byteLength(STUB_RETRY_MESSAGE)),
        });
        return origEnd(STUB_RETRY_MESSAGE);
      }
      return origEnd(body);
    }
    lastFullBundleAt = Date.now();
    lastFullBundleBytes = body.length;
    if (!res.headersSent) {
      origWriteHead(deferredStatusCode, {
        ...deferredHeaders,
        "Content-Type": deferredHeaders["Content-Type"] || "application/javascript",
        "Content-Length": String(body.length),
        "Cache-Control": "no-store, no-cache, must-revalidate",
      });
    }
    return origEnd(body);
  };
}

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

// LAN binding is via `expo start --host lan` (see Start-MobilePhoneMode.ps1).
config.server = {
  ...config.server,
  enhanceMiddleware: (middleware) => (req, res, next) => {
    const pathname = String(req.url || "").split("?")[0];
    if (pathname === "/.anai/build-id") {
      res.setHeader("Content-Type", "text/plain; charset=utf-8");
      res.setHeader("Cache-Control", "no-store, no-cache, must-revalidate");
      res.end(MOBILE_BUILD_ID);
      return;
    }
    if (pathname === "/.anai/bundle-ready") {
      const ready =
        lastFullBundleAt > 0
        && lastFullBundleBytes >= MIN_FULL_BUNDLE_BYTES
        && Date.now() - lastFullBundleAt < 300_000;
      res.setHeader("Content-Type", "text/plain; charset=utf-8");
      res.setHeader("Cache-Control", "no-store, no-cache, must-revalidate");
      res.end(ready ? `1:${lastFullBundleBytes}:${blockedStubCount}` : `0:${blockedStubCount}`);
      return;
    }
    res.setHeader("Cache-Control", "no-store, no-cache, must-revalidate");
    if (isBundleRequest(pathname) && !isIncrementalBundleRequest(req.url)) {
      bufferFullBundleResponse(req, res);
    }
    return middleware(req, res, next);
  },
};

module.exports = config;
