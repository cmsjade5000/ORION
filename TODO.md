# TODO

## TODO

- [ ] Task: Obtain production API gateway/middleware access or deployment details to complete auth enforcement, rate limiting, error handling, and security headers/CORS setup. **Part of:** Clawloan API Hardening
- [ ] Task: Explore opencode.ai integration by signing up for an API key and evaluating cloud session sharing, remote execution, and analytics features. **Part of:** Clawloan API Hardening
- [ ] Task: Implement LLM fallback logic to handle OpenAI out-of-funds errors (402), automatically switching to a backup provider or model. **Part of:** Clawloan API Hardening
- [ ] Task: Ensure Docker is installed and the gateway VM user has daemon access (e.g., add to the docker group) to enable container-based demos and builds. **Part of:** Clawloan API Hardening
- [ ] Task: Fix Telegram bots’ `/start` handlers and Privacy Mode settings so they respond correctly in DMs and groups (and simulate multi-agent chat via Orion using agent tags). **Part of:** Telegram Bot Group Chat Fix
- [ ] Task: Install the qmd-skill (Quick Markdown Search) for local hybrid search of Markdown notes and docs. **Part of:** QMD Memory Backend Implementation
- [ ] Task: Install `yq` on the gateway host (e.g. `sudo apt-get install -y yq` or `brew install yq`). **Part of:** Repo Mino Scan Improvement
- [ ] Task: Install the QMD CLI on the gateway host (e.g. `brew install qmd` or `npm install -g qmd`). **Part of:** QMD Memory Backend Prerequisites

- [ ] Obtain production API gateway/middleware access or deployment details to complete auth enforcement, rate limiting, error handling, and security headers/CORS setup (see `docs/security/clawloan-review.md`).
- [ ] Explore opencode.ai integration: sign up for an API key and evaluate cloud session sharing, remote execution, and analytics features.
- [ ] Implement LLM fallback logic to handle OpenAI out-of-funds errors (402), automatically switching to a backup provider or model.
- [ ] Ensure Docker is installed and user has daemon access (e.g., add to docker group) to enable container-based demos and builds.
- [ ] Investigate and fix Telegram bots’ `/start` handlers and Privacy Mode settings so they respond correctly in DMs and groups; meanwhile, simulate multi-agent chat via Orion using agent tags.
- [ ] Install qmd-skill (Quick Markdown Search) for local hybrid search of Markdown notes and docs to complement memory_search
- [ ] Install `yq` on the gateway host (e.g. `sudo apt-get install -y yq` or `brew install yq`) so the repo‑mino‑scan workflow can parse its configuration
- [ ] Install the QMD CLI on the gateway host (e.g. `brew install qmd` or `npm install -g qmd`) to enable full indexing in the QMD workspace memory backend
- [ ] Task: Configure macOS Remote Login (SSH), firewall, and port forwarding; then transfer the revivebot SSH key from server to local machine. **Part of:** AEGIS Key Transfer
