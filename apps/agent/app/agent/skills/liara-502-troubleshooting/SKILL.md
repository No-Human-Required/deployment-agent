---
name: liara-502-troubleshooting
description: Symptom to cause to fix map for Liara 502 Bad Gateway, crash loops, failed builds, stub pages and timeouts. Load when http_check is not 2xx.
---

# Troubleshooting a Liara app that does not serve

Liara's 502 page says: wrong port, app not on 0.0.0.0, check the events page,
or just wait for the service to become ready. Translate that into evidence:

## Always gather first
1. `liara_list_releases` - is the latest DEPLOY release `READY`, `BUILDING` or `FAILED`?
   - `BUILDING`: wait (`wait_seconds`) and re-check; do not redeploy.
   - `FAILED`: `liara_build_logs(release_id)`, fix the build.
2. `liara_runtime_logs` - last lines tell you if the process crashed.
3. `http_check` on `/` and on a health path (`/api/health`, `/health`).

## Symptom map
| Evidence in logs | Cause | Fix |
|---|---|---|
| `listening on 127.0.0.1` / `localhost:3000`, no crash | binds loopback | bind `0.0.0.0` in code, redeploy |
| app logs port N, release port M | port mismatch | redeploy with `port=N` or change code/`liara.json` to M |
| no "listening" line, process exits, `multirun: ... ended abnormally` | crash on boot | read the error line above it |
| `Cannot find module` / `MODULE_NOT_FOUND` | missing dep or wrong start path | add dep / fix `start` script / build output path |
| `Database \`X\` does not exist` | DATABASE_URL db name wrong | use the DB's real db name (Postgres default `postgres`) via `liara_connect_database` with `db_name` |
| `ECONNREFUSED`/`ENOTFOUND` to DB host | DB not on same private network, or wrong host | check `liara_list_databases`, reconnect via `liara_connect_database` |
| `Environment variable not found: X` / zod/joi env validation | missing env | `liara_set_envs` (ask the user for real secrets) |
| `EROFS: read-only file system` | writes outside disk | mount a disk and point the path env at it |
| `JavaScript heap out of memory` / OOMKilled | plan too small | ask the user to resize (paid) |
| 200 but body `ok <timestamp>` / hello world | a stub was deployed | deploy the real app folder |
| 404 on `/` but `/api/health` 200 | API-only deploy | serve the UI or tell the user the UI app is separate |
| Build: `nest: not found`, `tsc: not found` | CLI not installed | move to dependencies or ensure devDeps install |
| Build timeout | heavy build | build locally / `"build": {"location": "germany"}` |

## Rules
- One hypothesis per redeploy. Quote the log line that supports it.
- After an env change, the app restarts automatically; wait ~20-40 s then check.
- After a deploy, a Node app can take 30-90 s to become reachable; `http_check`
  with `wait_seconds` before declaring failure.
- If logs show the app is healthy but HTTP is still 502 after 2 minutes, the
  port is wrong.
