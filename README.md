# SyllabusAI

A RAG-based web app that lets students upload a course syllabus PDF and ask natural language questions about it. Built with a two-layer architecture that puts deterministic extraction *before* vector search — so "when is the midterm?" never wastes a token on retrieval.

**Live demo:** https://syllabus-ai-wapv.vercel.app

> The backend runs on Render's free tier and spins down after 15 minutes of inactivity, so the first upload after an idle period takes a few seconds longer while the process starts.

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

**Layer 2 — Semantic RAG:** For open-ended policy questions, the query is embedded with OpenAI `text-embedding-3-small` and matched against section-aware chunks in ChromaDB. Top-k results (k=4) go to Claude with a strict "only answer from context" prompt.

**Section-aware chunking:** PDFs are split at section headers first (regex: all-caps lines, lines ending in `:`), then sub-chunked at 800 chars with 50-char overlap. Each chunk carries `section_name`, `page_number`, and `chunk_index` metadata. This prevents late-policy text from bleeding into grading rubric text during retrieval.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Vector DB | ChromaDB (local persistent) |
| Embeddings | OpenAI `text-embedding-3-small` (API, no local model) |
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
pip install -r requirements.txt

cp .env.example .env
# Add your ANTHROPIC_API_KEY and OPENAI_API_KEY to .env

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
   - `ANTHROPIC_API_KEY` — your Anthropic key (structured extraction + RAG answers)
   - `OPENAI_API_KEY` — your OpenAI key (embeddings)
   - `ALLOWED_ORIGINS` — your Vercel frontend URL (e.g. `https://syllabusai.vercel.app`)
5. Deploy.

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

Free and starter tiers spin down after 15 minutes of inactivity, so the first request after a spin-down pays for the Python process starting up. There is no local model to load, so this is process start only, not model load.

### Embeddings are a network dependency

Embeddings moved from a local `sentence-transformers` model to the OpenAI API. That trade was deliberate:

**Gained:** no `torch` in the dependency tree, a much smaller image, a faster build, and a footprint that fits the free tier comfortably instead of borderline.

**Lost:** embedding is now a paid network call on the critical path of every upload. An upload embeds every chunk in one batch request, and there is no caching, so re-uploading the same PDF pays twice. If the OpenAI API is down or rate-limits, uploads fail. There are currently no timeouts or retries on either API client.

### Blocking work on the event loop

`POST /upload` is declared `async def` but does synchronous blocking work inside it (pdfplumber parsing, the embedding call, the Claude call). FastAPI runs `def` endpoints in a threadpool but runs `async def` endpoints directly on the event loop, so an in-flight upload blocks the whole server for its duration. `POST /query` is a plain `def` and is handled correctly.

Short-term fix is dropping the `async`. The right fix for real traffic is returning a job id immediately and doing ingestion on a worker.

### No evaluation set

`k=4`, the 800/50 chunk parameters, and the router's regex patterns were all chosen by inspection, not measurement. There is no labeled set of syllabi and expected answers, so retrieval quality and routing accuracy are unverified. This is the most important missing piece.

Two known routing weaknesses:

- The router falls through to RAG when a matched field is *empty*, but not when the match is *wrong*. "What grade do I need to pass?" matches the `grade_weights` pattern and confidently returns a grading breakdown.
- Chunks inherit `section["start_page"]`, the page the section header appeared on. A section spanning pages will cite the section's first page for text that is on a later one.
