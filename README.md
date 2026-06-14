# SyllabusAI

A RAG-based web app that lets students upload a course syllabus PDF and ask natural language questions about it. Built with a two-layer architecture that puts deterministic extraction *before* vector search — so "when is the midterm?" never wastes a token on retrieval.

**Live demo:** _coming soon_

---

## Architecture

Most RAG demos are just wrappers: input → LLM → output. SyllabusAI routes queries through two layers before the LLM is a last resort.

```
                        ┌─────────────────────────────────────────┐
  User question ──────▶ │           Query Router (regex)          │
                        └──────────┬──────────────────────────────┘
                                   │
               ┌───────────────────┴────────────────────┐
               │ pattern match?                          │ no match
               ▼                                         ▼
  ┌────────────────────────┐              ┌──────────────────────────┐
  │  Layer 1 – Structured  │              │  Layer 2 – Semantic RAG  │
  │  (deterministic)       │              │  (probabilistic)         │
  │                        │              │                          │
  │  SyllabusStructure     │              │  embed query             │
  │  (exam dates, grades,  │              │  → retrieve top-k chunks │
  │   instructor, policy…) │              │  → Claude answers        │
  │                        │              │    from context          │
  │  No LLM call needed    │              │                          │
  └────────────────────────┘              └──────────────────────────┘
               │                                         │
               └─────────────────┬───────────────────────┘
                                  ▼
                        { answer, layer_used }
```

**Layer 1 — Structured extraction:** On upload, a single Claude call (tool-use API, forced JSON schema) pulls typed fields — exam dates, deadlines, grade weights, late policy, office hours, instructor — into a `SyllabusStructure` dataclass. Stored in SQLite. Zero LLM cost per query after that.

**Layer 2 — Semantic RAG:** For open-ended policy questions, the query is embedded with `sentence-transformers/all-MiniLM-L6-v2` and matched against section-aware chunks in ChromaDB. Top-k results go to Claude with a strict "only answer from context" prompt.

**Section-aware chunking:** PDFs are split at section headers first (regex: all-caps lines, lines ending in `:`), then sub-chunked at 800 chars with 50-char overlap. Each chunk carries `section_name`, `page_number`, and `chunk_index` metadata. This prevents late-policy text from bleeding into grading rubric text during retrieval.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Vector DB | ChromaDB (local persistent) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| LLM | Anthropic Claude (`claude-haiku-4-5-20251001`) |
| PDF parsing | pdfplumber |
| Session storage | SQLite (stdlib) |
| Calendar export | icalendar |
| Frontend | React 19, Vite, TypeScript, Tailwind CSS v4 |
| Deployment | Render (backend) + Vercel (frontend) |

---

## Project Structure

```
syllabusai/
├── backend/
│   ├── main.py             # FastAPI app, routes
│   ├── ingest.py           # PDF parsing + section-aware chunking
│   ├── extract.py          # Layer 1: structured extraction (Claude tool-use)
│   ├── query.py            # Query router + RAG pipeline
│   ├── vector_store.py     # ChromaDB wrapper
│   ├── db.py               # SQLite session persistence
│   ├── calendar_export.py  # .ics generation
│   ├── models.py           # Pydantic models + SyllabusStructure dataclass
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   └── components/
│   │       ├── Upload.tsx
│   │       ├── Chat.tsx
│   │       └── StructuredSummary.tsx
│   └── package.json
├── render.yaml
├── vercel.json
└── README.md
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/upload` | Ingest PDF → `{ session_id, structured_summary }` |
| `POST` | `/query` | Ask a question → `{ answer, layer_used, source }` |
| `GET` | `/session/{id}/structure` | Raw `SyllabusStructure` JSON |
| `GET` | `/session/{id}/calendar` | Download `.ics` file |
| `GET` | `/session/{id}/ping` | Health-check a session (used by frontend on load) |
| `DELETE` | `/session/{id}` | Clean up session data |
| `GET` | `/health` | Render health check |

`layer_used` in query responses is `"structured"` or `"rag"` — the frontend surfaces this so users can see when an answer is deterministic vs. inferred.

---

## Local Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

uvicorn main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
# Create .env.local:
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev
# App available at http://localhost:5173
```

---

## Deployment

### Backend → Render

1. Push repo to GitHub.
2. In Render dashboard → **New Web Service** → connect repo.
3. Render will auto-detect `render.yaml`. Review and confirm.
4. Set environment variables in the Render dashboard:
   - `ANTHROPIC_API_KEY` — your Anthropic key
   - `ALLOWED_ORIGINS` — your Vercel frontend URL (e.g. `https://syllabusai.vercel.app`)
5. Deploy. First deploy takes ~5–10 minutes (installs torch + sentence-transformers).

### Frontend → Vercel

1. In Vercel dashboard → **New Project** → import repo.
2. Vercel will pick up `vercel.json` automatically.
3. Set environment variable:
   - `VITE_API_URL` — your Render backend URL (e.g. `https://syllabusai-backend.onrender.com`)
4. Deploy.

---

## Known Limitations

### Ephemeral filesystem on Render (important)

Render's free and starter tiers use an **ephemeral filesystem** — data written to disk is lost on every redeploy or restart. This affects two things:

| Data | Location | Lost on restart? |
|---|---|---|
| Vector chunks | `backend/chroma_db/` | **Yes** |
| Session structure | `backend/sessions.db` | **Yes** |

**What this means for users:** After a backend restart, existing `session_id` values stored in `localStorage` will 404 on the next query. The app handles this — `GET /session/{id}/ping` is called on page load, and a 404 response clears `localStorage` so the user sees the upload screen instead of a broken chat.

**Options to fix this properly:**

1. **Render Disk** ($7/mo add-on) — Mount a persistent disk at `/data`, point `chroma_db/` and `sessions.db` there. Zero code changes beyond updating the paths. Best option if you want sessions to survive restarts.

2. **Accept the limitation** — Sessions are inherently temporary (one syllabus, one conversation). The ping-on-load pattern handles it gracefully. Fine for a portfolio project.

3. **In-memory ChromaDB** — Switch from `PersistentClient` to `EphemeralClient` in `vector_store.py`. Makes the ephemerality explicit: data is never written to disk so there's no illusion of persistence. SQLite still needs the disk fix.

### Cold start latency

On first request after a Render spin-down (free/starter tiers spin down after 15 minutes of inactivity), the backend needs to:
- Start the Python process
- Load `sentence-transformers/all-MiniLM-L6-v2` into RAM (~90MB model)

Expect 20–40 seconds on the first request. Subsequent requests are fast.

### RAM usage

`torch` + `sentence-transformers` + `chromadb` + `fastapi` combined use ~400–500MB RAM. Render's free tier (512MB) is borderline. Use the **Starter plan** ($7/mo) for headroom. If you see OOM kills in Render logs, that's why.
