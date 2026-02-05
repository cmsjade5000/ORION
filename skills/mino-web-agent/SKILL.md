---
name: mino-web-agent
description: Automate and interact with real websites using the Mino Web Agent API for reliable, scalable web workflows.
homepage: https://docs.mino.ai
metadata:
  openclaw:
    emoji: "🌐"
    requires:
      env: [MINO_API_KEY]
    primaryEnv: MINO_API_KEY
---

# Mino Web Agent

Use this skill to drive a headless web agent capable of navigating pages, completing workflows across authenticated systems, and returning structured results via the Mino API.

## Usage Example

```bash
# Fetch product data from a storefront
node -e "
const { fetchWithMino } = require('./manifest');
fetchWithMino('https://example.com/products','products').then(console.log);
```
