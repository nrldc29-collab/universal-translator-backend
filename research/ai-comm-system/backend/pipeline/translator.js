const OpenAI = require("openai");
let openai = null;
let translatorStatus = { configured: false, last: 'not_configured' };
try {
  const apiKey = (process.env.OPENAI_API_KEY || '').trim();
  if (apiKey && !apiKey.includes('your_api')) {
    openai = new OpenAI({ apiKey });
    translatorStatus = { configured: true, last: 'configured' };
  }
} catch {
  translatorStatus = { configured: false, last: 'init_failed' };
}

async function translate(text, targetLanguage = 'es', sourceLanguage) {
  if (!text || !text.trim()) return '';
  if (!openai) {
    translatorStatus = { ...translatorStatus, last: 'not_configured' };
    return '';
  }
  const system = `You are a professional translator. Translate user input into ${targetLanguage}. Respond with translation only, no extra text.`;
  try {
    const res = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: text }
      ]
    });
    const out = res.choices?.[0]?.message?.content?.trim() || '';
    translatorStatus = { configured: true, last: out ? 'translated' : 'empty_model_response' };
    return out || text;
  } catch (e) {
    translatorStatus = {
      configured: true,
      last: 'openai_error',
      status: e?.status || null,
      code: e?.code || null,
      type: e?.type || null,
    };
  }
  return '';
}

function getTranslatorStatus() {
  return translatorStatus;
}

module.exports = { translate, getTranslatorStatus };
