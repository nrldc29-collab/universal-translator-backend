/**
 * Forwards stale Expo Go traffic on TCP 8081 to the active Metro port (usually 8082).
 * Phones that cached exp://HOST:8081 keep working without force-closing Expo Go.
 */
const http = require("http");

const listenPort = Number(process.env.ANAI_METRO_PROXY_PORT || 8081);
const targetPort = Number(process.env.ANAI_METRO_PORT || 8082);
const targetHost = process.env.ANAI_METRO_PROXY_TARGET || "127.0.0.1";
const lanHost = process.env.REACT_NATIVE_PACKAGER_HOSTNAME || "127.0.0.1";

function writeStubResponse(res, statusCode, message) {
  const body = String(message || "");
  res.writeHead(statusCode, {
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Content-Length": String(Buffer.byteLength(body)),
  });
  res.end(body);
}

const server = http.createServer((clientReq, clientRes) => {
  const headers = { ...clientReq.headers, host: `${targetHost}:${targetPort}` };
  const proxyReq = http.request(
    {
      hostname: targetHost,
      port: targetPort,
      path: clientReq.url,
      method: clientReq.method,
      headers,
    },
    (proxyRes) => {
      clientRes.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      proxyRes.pipe(clientRes);
    },
  );

  proxyReq.on("error", () => {
    writeStubResponse(
      clientRes,
      503,
      `Anai Metro is on port ${targetPort}. Open exp://${lanHost}:${targetPort} in Expo Go.`,
    );
  });

  clientReq.pipe(proxyReq);
});

server.listen(listenPort, "0.0.0.0", () => {
  console.log(`[anai] Metro proxy listening on 0.0.0.0:${listenPort} -> ${targetHost}:${targetPort}`);
});

server.on("error", (error) => {
  console.error("[anai] Metro proxy failed:", error?.message || error);
  process.exit(1);
});
