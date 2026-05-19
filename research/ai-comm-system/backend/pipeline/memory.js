const memory = {};

function saveMemory(sessionId, text) {
  if (!sessionId) return;
  if (!memory[sessionId]) memory[sessionId] = [];
  memory[sessionId].push({ ts: Date.now(), text });
}

function getMemory(sessionId) {
  return memory[sessionId] || [];
}

module.exports = { saveMemory, getMemory };
