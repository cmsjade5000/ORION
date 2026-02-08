#!/usr/bin/env node

const { listInboxes, listMessages, getMessage, sendMessage } = require('./manifest');

function usage() {
  console.error('Usage: node skills/agentmail/cli.js <cmd> [args...]');
  console.error('Commands:');
  console.error('  list-inboxes');
  console.error('  list-messages <inbox_id> [limit]');
  console.error('  get-message <inbox_id> <message_id>');
  console.error('  send <from_inbox_id> <to> <subject> <text...>');
  console.error('');
  console.error('Send (flag form):');
  console.error('  send --from <from_inbox_id> --to <to> --subject <subject> --text <text...>');
  console.error('');
  console.error('Examples:');
  console.error('  node skills/agentmail/cli.js list-inboxes');
  console.error('  node skills/agentmail/cli.js list-messages orion_gatewaybot@agentmail.to 10');
  console.error(
    '  node skills/agentmail/cli.js send orion_gatewaybot@agentmail.to you@example.com "Subject" "Hello from ORION"',
  );
  process.exit(2);
}

function parseFlagArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) {
      out._.push(a);
      continue;
    }
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next == null || next.startsWith('--')) {
      out[key] = true;
      continue;
    }
    out[key] = next;
    i++;
  }
  return out;
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
    const flags = parseFlagArgs(args);

    // Positional: send <from> <to> <subject> <text...>
    // Flag: send --from <from> --to <to> --subject <subject> --text <text...>
    const from =
      flags.from ??
      flags.inbox ??
      flags.inbox_id ??
      flags._[0];
    const to = flags.to ?? flags._[1];
    const subject = flags.subject ?? flags._[2];
    const text =
      flags.text ??
      (flags._.length >= 4 ? flags._.slice(3).join(' ') : null);

    if (!from || !to || !subject || !text) usage();

    const out = await sendMessage(from, { to, subject, text });
    console.log(JSON.stringify(out, null, 2));
    return;
  }

  usage();
}

main().catch((e) => {
  console.error(String(e && e.stack ? e.stack : e));
  process.exit(1);
});
