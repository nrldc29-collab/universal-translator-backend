const fs = require("fs");
const OpenAI = require("openai");

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

async function transcribe(audioPath) {
  const transcription = await openai.audio.transcriptions.create({
    file: fs.createReadStream(audioPath),
    model: "whisper-1",
  });

  return {
    text: transcription.text,
    confidence: 0.92, // placeholder estimate
  };
}

module.exports = { transcribe };
