require("./env").loadEnv();
const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const { processPipeline } = require("./pipeline/mediator");
const { getTranslatorStatus } = require("./pipeline/translator");
const { init } = require("./socket");
const { initNetwork } = require("./network");

const app = express();
const server = http.createServer(app);
const io = new Server(server);
const { recordEvent } = require("./services/analytics");
const client = require("prom-client");
const { Backpressure } = require('./services/backpressure');
const collectDefaultMetrics = client.collectDefaultMetrics;
collectDefaultMetrics();
app.use(express.json({ limit: '1mb' }));
const decisionCounter = new client.Counter({
  name: 'decisions_total',
  help: 'Total decisions made by mediator',
  labelNames: ['type']
});

// Brain API: accept { text, targetLanguage, sessionId } and return mediator output
app.post('/process', async (req, res) => {
  try {
    const payload = req.body || {};
    if (!payload || (typeof payload.text !== 'string' && !payload.audio)) {
      return res.status(400).json({ error: 'Invalid payload' });
    }
    const out = await processPipeline(payload);
    return res.json(out);
  } catch (e) {
    return res.status(500).json({ error: String(e?.message || e) });
  }
});
const errorCounter = new client.Counter({
  name: 'gateway_errors_total',
  help: 'Total errors thrown in gateway handling',
});
const decisionLatency = new client.Histogram({
  name: 'decision_latency_ms',
  help: 'Mediator decision latency in milliseconds',
  buckets: [10, 50, 100, 200, 400, 800, 1600, 3200]
});
const clarifyRatio = new client.Gauge({
  name: 'clarify_ratio',
  help: 'Ratio of clarifications to total decisions'
});
let totalDecisions = 0;
let clarifyDecisions = 0;

// Simple idempotency cache with TTL (60s)
const seen = new Map();
const IDEMP_TTL_MS = 60000;
setInterval(() => {
  const now = Date.now();
  for (const [k, v] of seen.entries()) {
    if (now - v > IDEMP_TTL_MS) seen.delete(k);
  }
}, 15000);

app.use(express.static("frontend"));

// Metrics endpoint for Prometheus
app.get("/metrics", async (_req, res) => {
  try {
    res.set("Content-Type", client.register.contentType);
    res.end(await client.register.metrics());
  } catch (e) {
    res.status(500).send(String(e?.message || e));
  }
});

// Health and readiness endpoints for probes
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', uptime_s: process.uptime() });
});
app.get('/ready', (_req, res) => {
  res.json({ ready: true });
});

app.get('/diagnostics/openai', (_req, res) => {
  res.json({ translator: getTranslatorStatus() });
});

io.on("connection", (socket) => {
  console.log("User connected");
  socket.on("disconnect", () => console.log("User disconnected"));

  // Heartbeat for client diagnostics
  socket.on('ping', () => socket.emit('pong'));

  const bp = new Backpressure(250);
  socket.on("message", async (data) => {
    try {
      bp.enqueue(1);
      // Basic validation
      if (!data || (typeof data.text !== 'string' && !data.audio)) {
        io.emit("message", { type: "error", message: "Invalid message payload" });
        return void bp.dequeue();
      }
      // Idempotency check
      const mid = data.id || data.messageId;
      if (mid) {
        if (seen.has(mid)) {
          // Send ack again; drop duplicate
          socket.emit('ack', { id: mid, status: 'duplicate' });
          return;
        }
        seen.set(mid, Date.now());
      }
      const start = Date.now();
      const result = await processPipeline(data);
      io.emit("message", result);
      // Ack to sender if message id provided
      if (mid) socket.emit('ack', { id: mid, status: 'ok' });
      // Record event outcome for analytics/evolution
      recordEvent({
        confused: result?.decision?.type === 'clarification',
        success: result?.decision?.type === 'response',
        latency: Date.now() - start,
      });
      if (result?.decision?.type) {
        decisionCounter.inc({ type: String(result.decision.type) }, 1);
        totalDecisions += 1;
        if (result.decision.type === 'clarification') clarifyDecisions += 1;
        if (totalDecisions > 0) clarifyRatio.set(clarifyDecisions / totalDecisions);
      }
      decisionLatency.observe(Date.now() - start);
      bp.dequeue();
    } catch (err) {
      io.emit("message", { type: "error", message: err?.message || "Pipeline error" });
      errorCounter.inc();
      try { bp.dequeue(); } catch {}
    }
  });
});

// Room-based messaging
init(io);

// Autonomous agent network (v3)
initNetwork(io);

server.listen(3000, () => {
  console.log("Server running on http://localhost:3000");
});

// Global error handlers for resilience
process.on('unhandledRejection', (e) => {
  console.error('unhandledRejection', e);
  errorCounter.inc();
});
process.on('uncaughtException', (e) => {
  console.error('uncaughtException', e);
  errorCounter.inc();
});

// Graceful shutdown
function shutdown() {
  console.log('Shutting down...');
  server.close(() => {
    console.log('HTTP server closed');
    process.exit(0);
  });
  setTimeout(() => process.exit(1), 5000).unref();
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
