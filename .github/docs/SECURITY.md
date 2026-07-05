# Security: 404 Fuzzer Detection & Automatic IP Ban

This document describes the automatic IP banning system that protects against fuzzing and directory scanning attacks.

> **Requires `RATE_LIMIT_ENABLED=true`** — the system is off by default. Set the environment variable to activate both rate limiting and 404 IP bans.

## Overview

When an IP repeatedly hits non-existent paths (`.env`, `.git/HEAD`, SSH keys, etc.), the system records each 404 as a "strike." Once a threshold is crossed, the IP is temporarily banned. Bans are persisted to a JSON file so they survive container restarts.

## Strike & Ban Algorithm

### Flow

```
Request → 404 → strike recorded → 3 strikes → 1h ban
                                → 5 strikes → 30d ban
```

### Thresholds

| Variable | Value | Description |
|----------|-------|-------------|
| `BAN_3_STRIKES_THRESHOLD` | 3 | 404 count → 1 hour ban |
| `BAN_5_STRIKES_THRESHOLD` | 5 | 404 count → 30 day ban |

Strikes older than 30 days (`STRIKE_WINDOW`) are pruned automatically.

### Key Behaviours

- **Strikes are per-worker** (in-memory), not shared across Gunicorn workers. Once any worker writes a ban to the JSON file, all workers see it on the next request.
- **Strikes accumulate across ban cycles.** If an IP gets 3 strikes (1h ban), then returns after the ban expires and gets 2 more 404s, the total becomes 5 → 30d ban.
- **Banned IPs receive `429 Too Many Requests`** with a human-readable `Retry-After` message.

## Log Format

### New ban issued
```
2026-07-05 11:02:22 [WARNING] 🚫 🟥 45.88.138.44: banned — 3 404 offenses (until 2026-07-05 12:02:22 UTC)
```

### Banned IP attempts access
```
2026-07-05 11:05:00 [WARNING] 🚫 🟥 45.88.138.44 GET /.env 429 🔴 banned until 2026-07-05 12:02:22 UTC
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `false` | Master switch — enables both Flask rate limiting and 404 IP ban detection |
| `BAN_FILE` | `banned_ips.json` | Path to the JSON file for persistent ban storage |

The entire system (rate limits + ban detection) is off by default. Set `RATE_LIMIT_ENABLED=true` to activate it.

### Docker Compose

Mount the file so bans survive container restarts:

```yaml
volumes:
  - /path/to/banned_ips.json:/app/banned_ips.json
```

## Manual Unban

Edit the JSON file and remove the IP entry from the `bans` object:

```json
{
  "version": 1,
  "bans": {
    "45.88.138.44": {
      "unban_at": "2026-08-04T11:00:00Z",
      "banned_at": "2026-07-05T11:00:27Z",
      "reason": "5+ 404 offenses (5+ strike threshold)"
    }
  }
}
```

Delete the entry and save. The next request from that IP will proceed normally.

## Source

Implementation is entirely in `app.py`:

- `_load_bans()` — reads `banned_ips.json`, skips expired bans
- `_save_bans()` — atomic write via tempfile + `os.replace`
- `_ban_ip()` — adds IP to in-memory ban dict, persists to file, logs
- `_prune_strikes()` — removes strikes older than `STRIKE_WINDOW`
- `@app.before_request` — checks ban before any route handler
- `@app.after_request` — records strikes on 404, triggers ban at threshold
