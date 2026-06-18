# Deploy & update workflow

Production layout: **frontend on Vercel**, **backend (api + db) on a VPS**,
fronted by a reverse proxy (Caddy) that terminates TLS for a public domain.
This doc covers the workflow only — actual VM IP/SSH credentials and rotated
secrets are kept in the team's local ops runbook, not in this repo.

## Architecture

```
browser ─► Vercel (Next.js, NEXT_PUBLIC_API_BASE=https://<api-domain>/api)
                              │
                              ▼
                    Caddy (reverse proxy, :80/:443, auto Let's Encrypt)
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              api:8000 (FastAPI)   db:5432 (Postgres+pgvector)
                                    not exposed publicly
```

If the VPS also hosts other unrelated projects, **don't run this repo's own
`caddy` service** if another Caddy instance already owns ports 80/443 on that
host — instead add a site block for the API domain to whichever Caddy
instance does own those ports, reverse-proxying to `<api-container-name>:8000`
(works automatically once that Caddy container joins this project's Docker
network, since Docker's embedded DNS resolves container names).

## First-time setup on a fresh VM

```bash
git clone <repo-url> greenflow && cd greenflow
cp .env.example .env
# edit .env: set a real POSTGRES_PASSWORD, LLM_KEYSTORE_SECRET, CORS_ORIGINS
# (comma-separated, must include your Vercel frontend origin), DOMAIN if this
# VM runs its own Caddy.

docker compose up -d --build db
docker compose ps                      # wait for "healthy"
docker compose up -d --build api
docker compose exec -T api python /app/scripts/seed_demo.py --days 7

docker compose up -d --build web       # only if this VM also serves the web UI
docker compose up -d caddy             # only if this VM owns ports 80/443
```

`db` is published via `expose:` only (no host port) by default — keep it that
way. Postgres should never be reachable from the public internet.

## Updating an existing deploy

```bash
cd /opt/<repo-dir>
git pull origin main

# rebuild only what changed
docker compose up -d --build api
docker compose up -d --build web    # if you also serve web from this VM
```

Check it worked:
```bash
docker compose ps
docker compose logs api --tail 50
curl -s https://<api-domain>/api/buildings
```

## Local dev → GitHub → VM update loop

1. Make changes locally, verify with `docker compose up -d --build` against
   the local stack (`docker-compose.yml` at repo root).
2. Commit with a message describing the *why*, push to `main`:
   ```bash
   git add <files>
   git commit -m "..."
   git push origin main
   ```
3. SSH into the VM, `git pull origin main`, rebuild only the changed
   service(s) (see above) — don't `docker compose up -d --build` the whole
   stack blindly on a shared VM, since that can also recreate services other
   projects don't expect touched.
4. Re-run `scripts/seed_demo.py` only if you need to reset demo data (it wipes
   and reseeds the fixed-UUID demo building — safe, but destructive to any
   manually-entered data under that building).

## Frontend (Vercel) env vars

- `NEXT_PUBLIC_API_BASE` — absolute URL to the backend, e.g.
  `https://greenflow-api.example.com/api`. Required because frontend and
  backend are different origins in production (no shared reverse proxy like
  in local dev) — a relative `/api` would resolve against Vercel itself.
- After changing env vars on Vercel, **redeploy** — `NEXT_PUBLIC_*` values are
  baked in at build time, not read at runtime.
- Backend `CORS_ORIGINS` (in the VM's `.env`) must include the exact Vercel
  origin, or the browser will block requests from the deployed frontend.
