---
name: liara-paas-node
description: How Liara builds and runs Node.js, NestJS, Next.js, Vite/React apps - package.json scripts, liara.json, port, 0.0.0.0 binding, Node version, monorepos.
---

# Node.js family on Liara PaaS

Source: docs.liara.ir/llms/paas/nodejs/*, /paas/nextjs/*, /paas/details/*.

## How the build runs
- Liara runs `npm ci` when a `package-lock.json` is uploaded, otherwise
  `npm install`; then `npm run build` **if a `build` script exists**, then `npm start`.
- `scripts.start` is **mandatory** (e.g. `"start": "node dist/main"`).
- Everything the app imports must be in `dependencies` or `devDependencies`
  of the deployed `package.json`. Workspace packages (`"@x/shared": "*"`) of a
  monorepo are NOT available unless you deploy from the monorepo root.
- What is uploaded (same as `liara deploy`): in every directory `.liaraignore`
  is used if present, else `.dockerignore`, else `.gitignore`. `.git`,
  `node_modules`, `.next`, `liara.json` and `.env*` are never uploaded.
  A `.liaraignore` REPLACES `.gitignore` for that directory, so copy the
  important `.gitignore` lines into it.
- The release shows `buildTimeoutMin` (`liara_list_releases`). A FAILED result
  whose duration is close to that limit is a timeout; a failure after a few
  seconds is a real error in that step.

## Silent build failures (log ends at a step with no error text)
Liara's build-log API often stops at the failing step, e.g. `> Running npm ci...`.
Do not guess: reproduce that exact step locally with `run_command`.
- `npm ci` fails fast when `package-lock.json` is out of sync with any
  `package.json` (root or workspaces), or was written by a much newer npm.
  Reproduce with `npm ci --dry-run` (or `npm ci`) in the deployed folder.
  Fix: `npm install` locally to refresh the lockfile, then redeploy; or drop the
  lockfile from the upload via `.liaraignore` so Liara uses `npm install`.
- Packages that download binaries (sharp, prisma engines, puppeteer, esbuild)
  can fail on the Iran build location: retry with
  `liara_deploy(..., build_location="germany")`.
- A corrupt build cache: retry once with `build_cache=false`.
- Node version mismatch (`engines`, `EBADENGINE`): pin it in `liara.json`
  (`"node": {"version": "22"}`). `liara_deploy` sends liara.json settings with the release.

## liara.json (project root of the deployed folder)
```json
{
  "port": 3000,
  "node": { "version": "22", "mirror": true },
  "build": { "location": "iran" }
}
```
- Do NOT put `app` in `liara.json`; `liara_deploy` already targets the app.
- `liara.json` is read by the deployer (not by Liara's server): `port`,
  `platform`, `disks`, `build.{location,cache,args}`, `node.{version,mirror}` and
  `healthCheck` are sent with the release. Explicit `liara_deploy` args win.
- For Next.js use `"next": { "mirror": true }` instead of `"node"`.
- `healthCheck` (optional): `{"command": "CMD curl --fail http://localhost:3000/api/health || exit 1", "interval": 30, "timeout": 15, "retries": 2, "startPeriod": 5}`.
  With zero-downtime + health check, a failing new release never receives traffic.

## Port and host (the #1 cause of 502)
- The app MUST listen on `0.0.0.0` and on the port given to the release
  (`liara_deploy(port=...)`, default 3000). Liara also sets env `PORT` only if
  you set it yourself — do not rely on it existing.
- NestJS: `await app.listen(process.env.PORT ?? 3000, '0.0.0.0');`
- Express: `app.listen(PORT, '0.0.0.0')`.
- Next.js: `next start` binds to 0.0.0.0 by default; `next start -p 3000`.
  A custom `server.js` must bind 0.0.0.0.
- Vite preview / dev servers bind to localhost by default: use
  `vite preview --host 0.0.0.0 --port 3000`, or better, serve the built static
  files from the API or deploy as a `static` platform app.

## NestJS specifics
- `"build": "nest build"`, `"start": "node dist/main"`. `@nestjs/cli` and
  `typescript` must be installed during build (devDependencies are installed).
- Global prefix (`app.setGlobalPrefix('api')`) makes `/` return 404; that is a
  routing fact, not a crash. Check what the user expects at `/`.
- Serving a SPA from Nest: `@nestjs/serve-static` with `rootPath` pointing at
  the built web assets and `exclude: ['/api*']`.

## Prisma
- `prisma generate` must run during build (`"build": "prisma generate && nest build"`
  or a `postinstall`). `prisma` CLI must be installed.
- Run migrations on boot: `"start": "prisma migrate deploy && node dist/main"`.
- Liara's root filesystem is read-only by default; write files only to a mounted
  disk path.

## Monorepo strategy
- Option A: deploy a single workspace folder (e.g. `apps/api`) — only works if it
  has no `workspace:*` / `*` deps on sibling packages.
- Option B: deploy the monorepo root with root scripts:
  `"build": "npm run build -w api && npm run build -w web"`,
  `"start": "npm run start -w api"`, and have the API serve the web build.
- Prefer B when the user expects one URL that shows the UI.
