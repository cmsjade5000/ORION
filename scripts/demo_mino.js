#!/usr/bin/env node

const { fetchWithMino } = require('../skills/mino-web-agent/manifest');

(async () => {
  try {
    console.log('Running Mino demo: fetching sample products...');
    const result = await fetchWithMino('https://example.com/products', 'products');
    console.log('Mino demo result:', JSON.stringify(result, null, 2));
  } catch (err) {
    console.error('Mino demo error:', err.message || err);
    process.exit(1);
  }
})();