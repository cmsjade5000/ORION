const fetch = require('node-fetch');

/**
 * Fetch data from a web page via Mino Web Agent API.
 * @param {string} url - The target page URL to navigate.
 * @param {string} template - The extraction template or workflow identifier.
 * @returns {Promise<object>} - Parsed JSON response from Mino.
 */
async function fetchWithMino(url, template) {
  const key = process.env.MINO_API_KEY;
  if (!key) {
    throw new Error('MINO_API_KEY environment variable is not set');
  }

  const response = await fetch('https://api.mino.ai/run', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${key}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ url, template })
  });

  if (!response.ok) {
    throw new Error(`Mino API error ${response.status}: ${response.statusText}`);
  }

  return await response.json();
}

module.exports = { fetchWithMino };