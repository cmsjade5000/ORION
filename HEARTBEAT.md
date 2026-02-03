# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.

- `0 2 * * *` scripts/nightly_review.py --dry-run  # Nightly Evolution Cron Job
- `0 0 * * *` scripts/rotate_memory.py  # Daily Memory rotation
