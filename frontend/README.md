# Seeytu-Xamleh — frontend

Vue 3 + Vite + TypeScript, with Vue Router and Pinia. Built from the redesign canvas (Baobab palette).

## Run it

Start the backend first (from `backend/`):

```bash
uv run fastapi dev src/backend/main.py   # http://localhost:8000
```

Then the frontend:

```bash
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

Vite proxies `/api` and `/users` to `http://localhost:8000`, so no CORS setup is needed.
Point it elsewhere with `BACKEND_URL=http://host:port npm run dev`.

Other scripts: `npm run build` (type-check + production build), `npm run typecheck`.

## What talks to the backend

| Screen | Endpoint |
|---|---|
| Sign in / Create account | `POST /users/login`, `POST /users/register` |
| New chat, follow-ups | `GET /api/websearch/ask?question=…` |

Not backed by the server yet, so kept in the browser (`localStorage`, per username):

- **Chats** — the conversation list and every answer with its sources.
- **Library** — built from the sources cited in your chats.

**Learning paths** shows what it will contain but isn't connected: there is no endpoint for it yet.

## Layout

```
src/
  api/          fetch wrapper + one module per backend area (auth, rag)
  stores/       Pinia: auth (token/session), chats (conversations, library)
  lib/          answer parser ([n] citations → buttons, no v-html), icons, storage
  components/   AppSidebar, ChatComposer, AssistantMessage, AnswerBody, SourceCard, AppIcon
  layouts/      AppShell (sidebar on desktop, drawer on phones)
  views/        SignIn, Home, Conversation, Library, LearningPaths
  styles/       tokens.css (every colour), base.css (buttons, inputs, tags), fonts.css
```
