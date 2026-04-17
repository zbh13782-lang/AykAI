# Testing AykAI React Frontend E2E

How to bring up the full stack and validate the React frontend (`frontend/`) end-to-end against the Go backend on `:9030` and the Python AI service on `:8000`.

## Devin Secrets Needed

- None for the default flow — the test user is pre-seeded in Postgres. See "Test credentials" below.
- For registration/email flow (out of default scope): `SMTP_EMAIL`, `SMTP_AUTHCODE`.
- For a real model behind the Python service: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL` (already provisioned in org env for this repo; test flow works without re-requesting them).

## Stack layout

- Go backend: `http://127.0.0.1:9030` (container `aykai-backend`)
- Python AI: `http://127.0.0.1:8000` (container `aykai-api`)
- Postgres: `chathistory` DB (container `aykai-postgres`) — NOT `AykAI`; the Go config `databaseName: chathistory` is the source of truth.
- Redis, Elasticsearch: supporting containers.
- Vite dev server: `http://127.0.0.1:5173`, proxies `/api` → `127.0.0.1:9030` via `frontend/vite.config.ts`.

## Bring-up

```bash
# From repo root
docker compose up -d --build python-api go-backend
# Wait for healthchecks:
docker ps --format '{{.Names}} {{.Status}}' | grep aykai

# Frontend dev server
cd frontend && npm install   # only on first run
nohup npm run dev -- --host 127.0.0.1 --port 5173 > /tmp/vite.log 2>&1 &
curl -sfo /dev/null -w 'vite=%{http_code}\n' http://127.0.0.1:5173/
```

## Test credentials (pre-seeded)

- `username`: `${AYKAI_TEST_USERNAME}.edu.cn`
- `password`: `123456` (MD5 hashed in DB: `e10adc3949ba59abbe56e057f20f883e`)

Smoke-test login without touching the UI:

```bash
curl -sS -X POST http://127.0.0.1:9030/api/v1/user/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"${AYKAI_TEST_USERNAME}.edu.cn","password":"123456"}'
# → {"status_code":1000,"status_msg":"success","token":"<JWT>"}
```

If login returns `CodeUserNotExist`, the seeded row is missing. Re-insert with:

```sql
INSERT INTO users (username, password)
VALUES ('${AYKAI_TEST_USERNAME}.edu.cn', 'e10adc3949ba59abbe56e057f20f883e')
ON CONFLICT DO NOTHING;
```

## Golden-path UI test (5 minutes, one recording)

1. Open `http://127.0.0.1:5173/` → redirects to `/login`.
2. Fill `用户名` + `密码` with seeded credentials, click `登录`. URL must become `/chat`, header shows `AykAI · <username>`.
3. Click `+ 新对话`. In the composer, type a question and press Enter.
4. Observe SSE streaming. Upload a small `.md` via `上传 Markdown` (toast appears for ~3.5s).
5. Click a prior session in the sidebar — right pane should swap to that session's history with no stale bubbles.

## The single adversarial assertion to watch for (SSE envelope)

The Go gateway forwards Python's `{"event":"token"|"references"|"done"|"error","data":...}` envelopes verbatim and prepends a `{"sessionId":"<uuid>"}` event on new sessions.

**Pass signal:** assistant bubble contains natural-language text only (e.g. Chinese answer tokens).
**Fail signal (broken `wrapStream`):** bubble contains `{"event":` / `"data":` / `[DONE]` literals, or the sidebar never gains a new session entry.

File to check first when this regresses: `frontend/src/api/chat.ts` (the `wrapStream` helper around `event`-based dispatch).

## Capturing the upload toast (it auto-dismisses)

`ChatPage.tsx`'s `showToast` timer is 3.5s, which is faster than our screenshot pipeline. Temporarily extend it **only in the browser** (production code unchanged) right after login:

```js
// In DevTools console, run BEFORE clicking upload:
const _st = window.setTimeout;
window.setTimeout = function (fn, ms) { if (ms === 3500) ms = 30000; return _st(fn, ms); };
```

Do not modify `ChatPage.tsx` for this — the console patch is sufficient and avoids touching source.

## Verifying network calls without a network panel

```js
performance.getEntriesByType('resource')
  .filter(e => e.name.includes('/api/'))
  .map(e => ({ url: e.name, dur: Math.round(e.duration) }));
```

Use this to confirm `POST /api/v1/AI/chat/send-stream-new-session` and `POST /api/v1/AI/chat/upload-md` fired and how long they took.

## Gotchas / things that might be broken and workarounds

- **Auth errors on SSE** come back as HTTP 200 + JSON envelope (`status_code: 2006/2007`), not 4xx. If `apiStream` silently ends with no tokens, check `frontend/src/api/client.ts` Content-Type JSON unwrap logic.
- **SMTP may be unconfigured** in test environments. Don't fight the registration flow — use the seeded account.
- **`wmctrl` is not installed** on the Devin desktop VM; don't rely on it for browser maximization. The Vite UI is simple enough that the default 1024×768 viewport works fine for screen recording.
- **Users table schema** — the login handler may accept either `username` or `email` as the identity column depending on backend changes; always smoke-test with curl first.
