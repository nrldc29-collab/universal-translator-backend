const { UserAgent } = require("./user_agent");
const { negotiate } = require("./negotiation");

const agents = {};

function getAgent(userId) {
  if (!agents[userId]) agents[userId] = new UserAgent(userId);
  return agents[userId];
}

async function processMessage(senderId, receiverId, message) {
  const senderAgent = getAgent(senderId);
  const receiverAgent = getAgent(receiverId);

  const senderContext = senderAgent.generateContext();
  const receiverContext = receiverAgent.generateContext();

  // Simulated interpretations — hook your mediator/LLM here
  const senderView = { text: message, confidence: 0.85, context: senderContext };
  const receiverView = { text: message, confidence: 0.75, context: receiverContext };

  const final = negotiate(senderAgent, receiverAgent, senderView, receiverView);

  senderAgent.updateMemory(final);
  receiverAgent.updateMemory(final);

  return final;
}

module.exports = { processMessage };
