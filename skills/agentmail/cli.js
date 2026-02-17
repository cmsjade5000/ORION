#!/usr/bin/env node

const fs = require('fs');
const { listInboxes, listMessages, getMessage, sendMessage } = require('./manifest');

function usage() {
  console.error('Usage: node skills/agentmail/cli.js <cmd> [args...]');
  console.error('Commands:');
  console.error('  list-inboxes');
  console.error('  list-messages <inbox_id> [limit]');
  console.error('  get-message <inbox_id> <message_id>');
  console.error('  send <from_inbox_id> <to> <subject> <text...>');
  console.error('  reply-last <from_inbox_id> <text...> [--from <match_sender_email>]');
  console.error('');
  console.error('Send (flag form):');
  console.error('  send --from <from_inbox_id> --to <to> --subject <subject> --text <text...>');
  console.error('  send --from <from_inbox_id> --to <to> --subject <subject> --text-file <path>');
  console.error('  send --from <from_inbox_id> --to <to> --subject <subject> --text-file <path> --html-file <path>');
  console.error('Reply-last (flag form):');
  console.error('  reply-last --from <from_inbox_id> --text <text...> [--from-email <sender_email>]');
  console.error('  reply-last --from <from_inbox_id> --text-file <path> [--from-email <sender_email>]');
  console.error('');
  console.error('Examples:');
  console.error('  node skills/agentmail/cli.js list-inboxes');
  console.error('  node skills/agentmail/cli.js list-messages orion_gatewaybot@agentmail.to 10');
  console.error(
    '  node skills/agentmail/cli.js send orion_gatewaybot@agentmail.to you@example.com "Subject" "Hello from ORION"',
  );
  console.error(
    '  node skills/agentmail/cli.js reply-last orion_gatewaybot@agentmail.to "confirmed" --from boughs.gophers-2t@icloud.com',
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

function extractEmail(s) {
  if (!s) return null;
  const str = String(s).trim();
  // Common: "Name <email@domain>"
  const m = str.match(/<([^>]+@[^>]+)>/);
  if (m) return m[1].trim();
  // Otherwise, try a loose match.
  const m2 = str.match(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i);
  return m2 ? m2[0] : null;
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
    const textFile = flags['text-file'] ?? flags.text_file ?? flags.textFile ?? null;
    const htmlFile = flags['html-file'] ?? flags.html_file ?? flags.htmlFile ?? null;
    const html =
      (htmlFile ? fs.readFileSync(String(htmlFile), 'utf8') : null) ??
      flags.html ??
      null;
    const text =
      (textFile ? fs.readFileSync(String(textFile), 'utf8') : null) ??
      flags.text ??
      (flags._.length >= 4 ? flags._.slice(3).join(' ') : null);

    if (!from || !to || !subject || !text) usage();

    const out = await sendMessage(from, { to, subject, text, ...(html ? { html } : {}) });
    console.log(JSON.stringify(out, null, 2));
    return;
  }

  if (cmd === 'reply-last') {
    const flags = parseFlagArgs(args);
    const inboxId = flags.from ?? flags._[0];
    const matchFrom =
      flags['from-email'] ??
      flags.from_email ??
      flags.fromEmail ??
      flags.sender ??
      flags.match_from ??
      flags.matchFrom ??
      flags.fromMatch ??
      flags.from_addr ??
      flags.fromAddr;
    // Note: flags.from is used for inboxId above; also accept --from-email for sender match.
    const textFile = flags['text-file'] ?? flags.text_file ?? flags.textFile ?? null;
    const text =
      (textFile ? fs.readFileSync(String(textFile), 'utf8') : null) ??
      flags.text ??
      (flags._.length >= 2 ? flags._.slice(1).join(' ') : null);
    if (!inboxId || !text) usage();

    const out = await listMessages(inboxId, { limit: 20 });
    const messages = out.messages ?? [];

    const wanted = matchFrom ? String(matchFrom).trim().toLowerCase() : null;
    const pick = messages.find((m) => {
      const labels = Array.isArray(m.labels) ? m.labels : [];
      if (!labels.includes('received')) return false;
      if (!wanted) return true;
      const fromEmail = extractEmail(m.from);
      return fromEmail && fromEmail.toLowerCase() === wanted;
    });

    if (!pick) {
      throw new Error(
        wanted
          ? `No received messages found matching sender ${wanted}`
          : 'No received messages found in the last 20 messages',
      );
    }

    const to = extractEmail(pick.from);
    if (!to) throw new Error(`Could not parse sender email from: ${pick.from}`);

    const subject = pick.subject ? `Re: ${pick.subject}` : 'Re: (no subject)';
    const sent = await sendMessage(inboxId, { to, subject, text });
    console.log(
      JSON.stringify(
        {
          repliedTo: {
            message_id: pick.message_id ?? null,
            thread_id: pick.thread_id ?? null,
            from: pick.from ?? null,
            subject: pick.subject ?? null,
            timestamp: pick.timestamp ?? null,
          },
          sent,
        },
        null,
        2,
      ),
    );
    return;
  }

  usage();
}

main().catch((e) => {
  console.error(String(e && e.stack ? e.stack : e));
  process.exit(1);
});
