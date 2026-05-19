const fs = require('fs');
const path = require('path');

function loadEnv(file = path.resolve(__dirname, '..', '.env')) {
  if (!fs.existsSync(file)) return;
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const index = trimmed.indexOf('=');
    if (index < 0 && trimmed.startsWith('sk-')) {
      process.env.OPENAI_API_KEY = trimmed;
      continue;
    }
    if (index <= 0) continue;
    const key = trimmed.slice(0, index).trim().replace(/^export\s+/, '');
    let value = trimmed.slice(index + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}

module.exports = { loadEnv };
