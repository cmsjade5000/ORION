#!/usr/bin/env node

const { listInboxes, listMessages, getMessage, sendMessage } = require('./manifest');

function usage() {
  console.error('Usage: node skills/agentmail/cli.js <cmd> [args...]');
  console.error('Commands:');
  console.error('  list-inboxes');
  console.error('  list-messages <inbox_id> [limit]');
  console.error('  get-message <inbox_id> <message_id>');
  console.error('  send <inbox_id> <to> <subject> <text>');
  process.exit(2);
}

async function main() {
  const [cmd, ...args] = process.argv.slice(2);
  if (!cmd) usage();

  if (cmd === 'list-inboxes') {
    const out = await listInboxes({ limit: 50 });
    console.log(JSON.stringify(out, null, 2));
    return;
  }

  if (cmd === 'list-messages') {
    const inboxId = args[0];
    const limit = args[1] ? Number(args[1]) : 20;
    if (!inboxId) usage();
    const out = await listMessages(inboxId, { limit });
    console.log(JSON.stringify(out, null, 2));
    return;
  }

  if (cmd === 'get-message') {
    const inboxId = args[0];
    const messageId = args[1];
    if (!inboxId || !messageId) usage();
    const out = await getMessage(inboxId, messageId);
    console.log(JSON.stringify(out, null, 2));
    return;
  }

  if (cmd === 'send') {
    const inboxId = args[0];
    const to = args[1];
    const subject = args[2];
    const text = args.slice(3).join(' ');
    if (!inboxId || !to || !subject || !text) usage();
    const out = await sendMessage(inboxId, { to, subject, text });
    console.log(JSON.stringify(out, null, 2));
    return;
  }

  usage();
}

main().catch((e) => {
  console.error(String(e && e.stack ? e.stack : e));
  process.exit(1);
});
