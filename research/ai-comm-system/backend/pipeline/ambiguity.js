const TERMS = [
  "bank", "set", "run", "charge", "fine", "case", "fair", "light",
  "right", "note", "check", "bat", "spring", "match"
];

function detectAmbiguity(text) {
  const t = (text || "").toLowerCase();
  if (!t) return { high: false, words: [], score: 0 };
  const re = new RegExp(`\\b(${TERMS.join('|')})\\b`, 'gi');
  const hits = new Set();
  let m;
  while ((m = re.exec(t)) !== null) {
    hits.add(m[1].toLowerCase());
  }
  const count = hits.size;
  const punctuation = (t.includes('?') ? 1 : 0) + (t.includes('...') ? 1 : 0);
  const score = Math.min(1, count * 0.25 + punctuation * 0.1);
  return { high: score > 0.6, words: Array.from(hits), score };
}

module.exports = { detectAmbiguity };
