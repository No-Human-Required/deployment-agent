---
name: liara-dbaas-and-envs
description: Liara managed databases (Postgres, MySQL, MongoDB, Redis), private network, connection URLs, and environment variables.
---

# Databases and envs on Liara

Source: docs.liara.ir/llms/dbaas/*, /paas/details/envs.md, /paas/details/private-network.md.

## Private network
- Apps and databases on the same private network talk over the internal host
  (the DB `hostname`, e.g. `my-db`) with the internal port. No public access
  needed. A DB on a different network is unreachable from the app.

## Connection URLs
- Postgres: `postgresql://root:<password>@<host>:5432/<db>`; the default database
  name is `postgres`. Prisma needs `?schema=public` sometimes.
- MySQL/MariaDB: `mysql://root:<password>@<host>:3306/<db>`.
- MongoDB: `mongodb://root:<password>@<host>:27017/<db>?authSource=admin`.
- Redis: `redis://:<password>@<host>:6379/0`.
- Use `liara_connect_database(database_id, env_key, db_name)`; it builds the URL
  server-side with the real password and sets the env. You never see the password.

## Creating a database
- `liara_create_database` is paid and requires the user's approval (the run
  pauses for it). Before creating, check `liara_list_databases` - reuse an
  existing one when it fits.
- New databases take 1-3 minutes to become ready.

## Env vars
- `liara_set_envs` merges keys into the app's envs and triggers an `ENV_UPDATE`
  release (automatic restart). No source redeploy needed.
- Read current keys with `liara_get_project` (values are redacted for you).
- Never invent real secrets (SMTP passwords, API keys). If the app needs them
  and they are missing, ask the user in the final message, but still make
  everything else work.
- Generated secrets (JWT secret, session secret, VAPID keys) may be generated
  with `generate_secret`.
