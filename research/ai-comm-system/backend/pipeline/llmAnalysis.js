const OpenAI = require("openai");
const apiKey = (process.env.OPENAI_API_KEY || '').trim();
const openai = apiKey && !apiKey.includes('your_api') ? new OpenAI({ apiKey }) : null;

function extractJson(s) {
  if (!s) return null;
  // Try to find first JSON object in the string
  const start = s.indexOf('{');
  const end = s.lastIndexOf('}');
  if (start !== -1 && end !== -1 && end > start) {
    const slice = s.substring(start, end + 1);
    try { return JSON.parse(slice); } catch {}
  }
  // Try codefence ```json blocks
  const match = s.match(/```json\s*([\s\S]*?)```/i);
  if (match) {
    try { return JSON.parse(match[1]); } catch {}
  }
  return null;
}

async function analyze(text, context = {}) {
  const fallback = () => {
    const t = (text || '').toLowerCase();
    return {
      intent: t.includes('why') ? 'question' : (t.includes('how much') ? 'price' : 'general'),
      emotion: 'neutral',
      entities: [],
      ambiguity_score: 0.3,
      urgency: t.includes('now') ? 0.8 : 0.2,
    };
  };
  if (!openai) {
    // Safe local heuristic when LLM is unavailable
    return fallback();
  }
  const prompt = `Extract structured communication data as JSON (strictly JSON, no prose).
Text: "${text}"
Return: {"intent":"...","emotion":"...","entities":[],"ambiguity_score":0-1,"urgency":0-1}`;
  try {
    const res = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: prompt }],
      temperature: 0,
    });
    const raw = res.choices?.[0]?.message?.content?.trim() || "{}";
    const parsed = extractJson(raw);
    if (parsed) return parsed;
  } catch {}
  return fallback();
}

module.exports = { analyze };
