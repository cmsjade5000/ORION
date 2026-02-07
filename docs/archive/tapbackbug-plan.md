# Plan: Fix Telegram Tapback Reactions

**Generated:** 2026-02-05

## Overview
Investigate and fix the `message` tool reaction failures in Telegram group topics. The error `400: Bad Request: message to react not found` suggests incorrect message IDs or missing thread IDs when reacting in forum topics.

## Prerequisites
- Access to `openclaw.yaml` (Telegram config)
- `docs/TELEGRAM_STYLE_GUIDE.md` (Review existing docs)
- `src/plugins/telegram/index.ts` (or relevant plugin code if available to inspect payload construction)

## Tasks

### T1: Research Telegram API Requirements for Topics
- **depends_on**: []
- **description**: Research Telegram Bot API `setMessageReaction` requirements for forum topics. Specifically, does it require `message_thread_id`?
- **validation**: Documentation snippet confirming parameters.

### T2: Create Reproduction Test Case
- **depends_on**: [T1]
- **description**: Create a manual test script using `curl` or a small JS script to hit the Telegram API directly with various payloads (with/without thread_id) to identify the working shape.
- **validation**: Successful reaction on a specific message in Topic 1.

### T3: Diagnose OpenClaw Message Tool
- **depends_on**: [T2]
- **description**: Inspect how the `message` tool constructs the Telegram payload. Identify if it strips or omits `message_thread_id` when `action: react` is called.
- **validation**: Root cause identified (e.g., "Plugin drops thread_id").

### T4: Implement Fix or Workaround
- **depends_on**: [T3]
- **description**: If a code fix is needed (and we can edit source), patch the plugin. If configuration or usage pattern is wrong (e.g. need to pass `threadId` arg explicitly), document the correct usage.
- **validation**: `openclaw message --action react ...` works in Topic 1.

### T5: Verify and Document
- **depends_on**: [T4]
- **description**: Test the fix live in chat. Update `docs/TELEGRAM_STYLE_GUIDE.md` with the correct protocol for reacting in topics.
- **validation**: ORION successfully reacts to a user message in the topic.

