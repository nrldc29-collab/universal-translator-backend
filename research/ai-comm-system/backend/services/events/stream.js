const Redis = require("ioredis");
const redis = new Redis(process.env.REDIS_URL || "redis://localhost:6379");

const STREAM = "ai_events";

async function publish(event) {
  await redis.xadd(STREAM, "*", "data", JSON.stringify(event));
}

async function consume(handler) {
  let lastId = "$";
  // simple consumer loop; in production use consumer groups
  // and robust error handling
  // BLOCK 5000ms for demo polling
  // Note: this is a basic example; scale with XGROUP/XREADGROUP
  // and manual acks for reliability
  // eslint-disable-next-line no-constant-condition
  while (true) {
    // blocking read
    const results = await redis.xread("BLOCK", 5000, "STREAMS", STREAM, lastId);
    if (!results) continue;
    for (const [, messages] of results) {
      for (const [id, fields] of messages) {
        lastId = id;
        try {
          const event = JSON.parse(fields[1]);
          await handler(event);
        } catch (e) {
          // swallow malformed events for now; add dead-letter queue in prod
          // console.error('event handler error', e);
        }
      }
    }
  }
}

module.exports = { publish, consume };
