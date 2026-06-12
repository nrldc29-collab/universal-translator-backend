const { chromium } = require('playwright');

const targetUrl = process.argv[2] || 'http://127.0.0.1:5173/';

(async () => {
  const errors = [];
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
  });
  await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(35000);
  console.log(JSON.stringify([...new Set(errors)], null, 2));
  await browser.close();
})().catch((e) => {
  console.error('runner failed:', e);
  process.exit(1);
});
