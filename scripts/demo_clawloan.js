#!/usr/bin/env node
const path = require('path');
const { fetchManifest } = require(path.resolve(__dirname, '../skills/clawloan/manifest.js'));

(async () => {
  try {
    const apiUrl = process.env.CLAWLOAN_API_URL;
    const botId = process.env.CLAWLOAN_BOT_ID;
    if (!apiUrl || !botId) {
      throw new Error('Environment variables CLAWLOAN_API_URL and CLAWLOAN_BOT_ID are required');
    }
    console.log(`CLAWLOAN_API_URL=${apiUrl}`);
    console.log(`CLAWLOAN_BOT_ID=${botId}`);

    console.log('\nFetching skill.json via manifest loader...');
    const skillManifest = await fetchManifest(`${apiUrl}/skill.json`, 'skill.json');
    console.log('skill.json content:');
    console.log(skillManifest);

    console.log('\nCalling /api/health endpoint...');
    const healthResponse = await fetch(`${apiUrl}/api/health`);
    const healthData = await healthResponse.json();
    console.log('/api/health response:');
    console.log(healthData);

    console.log('\nCalling /api/pools endpoint...');
    const poolsResponse = await fetch(`${apiUrl}/api/pools`);
    const poolsData = await poolsResponse.json();
    console.log('/api/pools response:');
    console.log(poolsData);

    process.exit(0);
  } catch (err) {
    console.error('Error in demo_clawloan:', err);
    process.exit(1);
  }
})();
