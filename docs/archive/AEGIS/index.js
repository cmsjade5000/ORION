#!/usr/bin/env node

import TelegramBot from 'node-telegram-bot-api';
import { execSync } from 'child_process';

// Load config
const token = process.env.AEGIS_TELEGRAM_TOKEN;
const chatId = process.env.AEGIS_TELEGRAM_CHAT_ID;
const intervalMs = parseInt(process.env.CHECK_INTERVAL_MS, 10) || 60000;

if (!token || !chatId) {
  console.error('AEGIS_TELEGRAM_TOKEN and AEGIS_TELEGRAM_CHAT_ID must be set');
  process.exit(1);
}

// Initialize bot
const bot = new TelegramBot(token, { polling: true });

// Define bot commands for Telegram UI
bot.setMyCommands([
  { command: 'start', description: 'Register and confirm AEGIS is online' },
  { command: 'status', description: 'Get current AEGIS health status' },
]).catch(console.error);

// Log all incoming messages for debugging
bot.on('message', (msg) => {
  console.log('AEGIS received message:', JSON.stringify(msg));
});


bot.onText(/\/start/, (msg) => {
  const incomingId = msg.chat.id.toString();
  if (!chatId) {
    bot.sendMessage(incomingId, `AEGIS ready. Your chat ID (${incomingId}) has been registered.`);
    // Persist chat ID for future use
    import('fs').then(fs => {
      fs.appendFileSync('.env', `AEGIS_TELEGRAM_CHAT_ID=${incomingId}\n`);
    });
  } else if (incomingId === chatId) {
    bot.sendMessage(chatId, 'AEGIS is online and monitoring ORION.');
  }
});

bot.on('polling_error', (err) => console.error('Polling error:', err));

console.log(`AEGIS starting health monitor with interval ${intervalMs} ms`);

let failureCount = 0;
setInterval(() => {
  try {
    // Simple health check: ping ORION health endpoint
    const out = execSync('curl -s -m 5 https://ORION_PUBLIC_OR_TUNNELED_URL/health');
    if (out.toString().includes('"status":"ok"')) {
      console.log(`AEGIS successful health check at ${new Date().toISOString()}`);
      failureCount = 0;
    } else {
      throw new Error('unexpected response');
    }
  } catch (e) {
    failureCount++;
    console.log(`AEGIS health check failure #${failureCount}`);
    if (failureCount >= 3) {
      bot.sendMessage(chatId, 'ORION is down. Attempting restart...');
      execSync('ssh -i ~/.ssh/revivebot_key revivebot@localhost "systemctl restart openclaw-gateway.service"');
      bot.sendMessage(chatId, 'Restart command issued for ORION.');
      failureCount = 0;
    }
  }
}, intervalMs);
