const sessions = {};
const { processPipeline } = require("./pipeline/mediator");

function init(io) {
  io.on("connection", (socket) => {
    socket.on("join", (roomId) => {
      socket.join(roomId);
      if (!sessions[roomId]) sessions[roomId] = [];
    });

    socket.on("message", async (data) => {
      const roomId = data.roomId || "default";
      const result = await processPipeline(data);
      sessions[roomId].push(result);
      io.to(roomId).emit("message", result);
    });
  });
}

module.exports = { init };
