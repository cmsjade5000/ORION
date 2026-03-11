# Telegram Topic Routing (ORION)

Goal: route Telegram forum topics to dedicated agents with isolated sessions.

## Why

- Better specialist isolation (ATLAS/LEDGER/EMBER topics do not share ORION main context)
- Cleaner operational ownership per topic
- Durable, explicit routing state in runtime config

## Canonical Topic Peer ID

For bindings and diagnostics, use:

- `<chatId>:topic:<topicId>`

Example:

- `-1001234567890:topic:7`

## Topic Mapping Strategy

Recommended baseline:

- Topic `1` (General) -> `main`
- Topic `7` (Ops) -> `atlas`
- Topic `9` (Money) -> `ledger`
- Topic `11` (Support) -> `ember`

Use your real topic IDs from Telegram forum threads.

## Runtime Config Shape

Set per-topic routing in runtime config:

```json5
{
  channels: {
    telegram: {
      groups: {
        "-1001234567890": {
          topics: {
            "1": { agentId: "main" },
            "7": { agentId: "atlas" },
            "9": { agentId: "ledger" },
            "11": { agentId: "ember" }
          }
        }
      }
    }
  }
}
```

## Apply With Bootstrap Script

Dry-run:

```bash
scripts/telegram_topic_bindings_bootstrap.sh \
  --group-id -1001234567890 \
  --topic 1:main \
  --topic 7:atlas \
  --topic 9:ledger \
  --topic 11:ember
```

Apply:

```bash
scripts/telegram_topic_bindings_bootstrap.sh \
  --group-id -1001234567890 \
  --topic 1:main \
  --topic 7:atlas \
  --topic 9:ledger \
  --topic 11:ember \
  --apply
```

This script updates:

- `channels.telegram.groups.<chatId>.topics.<topicId>.agentId`

and ensures topic-scoped agent bindings:

- `openclaw agents bind --agent <agent> --bind telegram:<chatId>:topic:<topicId>`

## Verification

```bash
openclaw config validate --json
openclaw config get channels.telegram
openclaw agents bindings --json
openclaw channels status --probe
```

Optional smoke test:

1. Send one test message in each configured topic.
2. Confirm session keys route to expected agent namespace.

## Rollback

1. Remove topic mapping keys:

```bash
openclaw config unset 'channels.telegram.groups["-1001234567890"].topics["7"].agentId'
openclaw config unset 'channels.telegram.groups["-1001234567890"].topics["9"].agentId'
openclaw config unset 'channels.telegram.groups["-1001234567890"].topics["11"].agentId'
```

2. Revalidate config:

```bash
openclaw config validate --json
```

3. If needed, unbind agent account routes:

```bash
openclaw agents unbind --agent atlas --bind 'telegram:-1001234567890:topic:7'
openclaw agents unbind --agent ledger --bind 'telegram:-1001234567890:topic:9'
openclaw agents unbind --agent ember --bind 'telegram:-1001234567890:topic:11'
```
