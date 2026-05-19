const { processMessage } = require("./agents/orchestrator");

function initNetwork(io) {
  io.on("connection", (socket) => {
    socket.on("message", async (data) => {
      const result = await processMessage(data.senderId || "alice", data.receiverId || "bob", data.text || "");
      io.emit("message", result);
    });
  });
}

module.exports = { initNetwork };
