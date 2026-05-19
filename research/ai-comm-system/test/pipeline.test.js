const test = require('node:test');
const assert = require('node:assert/strict');

process.env.OPENAI_API_KEY = 'your_api_key_here';

const { detectAmbiguity } = require('../backend/pipeline/ambiguity');
const { decide } = require('../backend/pipeline/brain');
const { processPipeline } = require('../backend/pipeline/mediator');
const { translate, getTranslatorStatus } = require('../backend/pipeline/translator');

test('detectAmbiguity matches ambiguous whole words only', () => {
  const hit = detectAmbiguity('I need to go to the bank right now.');
  const miss = detectAmbiguity('The banking app is working.');

  assert.equal(hit.words.includes('bank'), true);
  assert.equal(miss.words.includes('bank'), false);
});

test('detectAmbiguity marks multi-ambiguous utterances as high ambiguity', () => {
  const result = detectAmbiguity('bank right fine charge');

  assert.equal(result.high, true);
  assert.equal(result.score, 1);
  assert.deepEqual(result.words.sort(), ['bank', 'charge', 'fine', 'right']);
});

test('brain requests clarification for high ambiguity', () => {
  const decision = decide({ confidence: 0.9, ambiguity: 1, intent: 'general' });

  assert.equal(decision.type, 'clarification');
});

test('translator safely returns empty translation when OpenAI is not configured', async () => {
  const result = await translate('Hello, how are you today?', 'es');

  assert.equal(result, '');
  assert.equal(getTranslatorStatus().last, 'not_configured');
});

test('processPipeline returns clarification without OpenAI for ambiguous input', async () => {
  const result = await processPipeline({ text: 'bank right fine charge', targetLanguage: 'es', sessionId: 'test-session' });

  assert.equal(result.text, 'bank right fine charge');
  assert.equal(result.translated, '');
  assert.equal(result.targetLanguage, 'es');
  assert.equal(result.decision.type, 'clarification');
  assert.equal(result.analysis.local_ambiguity.high, true);
});
