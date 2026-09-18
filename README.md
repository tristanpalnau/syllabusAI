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

## Trade-offs and Known Limitations

Everything below is a decision I made knowingly, with what I gave up to get it.

### Embeddings: local model vs. hosted API

I originally embedded with a local `sentence-transformers/all-MiniLM-L6-v2` model and moved to the OpenAI API.

What that bought: no `torch` in the dependency tree, a much smaller image, a faster build, and a memory footprint that fits the free tier comfortably instead of sitting right at the edge of an OOM kill.

What it cost: embedding is now a paid network call on the critical path of every upload, so an upload fails if the OpenAI API does. There is no embedding cache, so re-uploading the same PDF pays twice. Neither API client has timeouts or retries configured yet.

For a single-syllabus-per-session workload the request volume is low and the reliability trade is worth it. At higher volume I would cache embeddings keyed by a content hash of the chunk.

### Session data does not survive a restart

Render's free and starter tiers use an ephemeral filesystem, so both the Chroma directory and the SQLite file are wiped on every redeploy or spin-down.

| Data | Location | Survives restart? |
|---|---|---|
| Vector chunks | `backend/chroma_db/` | No |
| Session structure | `backend/sessions.db` | No |

The failure this produces is subtle: the browser still holds a `session_id` in `localStorage`, so the app restores a chat view for a session the server no longer knows about, and every question 404s. I handle it with `GET /session/{id}/ping`, which the frontend calls before restoring. A 404 clears `localStorage` and drops the user back to the upload screen.

That is containment, not a fix. I chose it deliberately: a syllabus session is one document and one conversation, so it is arguably ephemeral by nature, and paying $7/mo for a Render Disk to persist it is not worth it for this project. If I did want persistence, the disk mount is the answer and costs nothing but a path change. The other honest option is switching Chroma to `EphemeralClient` so the code stops implying a durability it does not have.

### Cold start latency

Free and starter tiers spin down after 15 minutes of inactivity, so the first request after an idle period waits on the Python process starting. There is no model to load into memory, so this is process start only.

### Ingestion blocks the event loop

`POST /upload` is declared `async def` but the work inside it is synchronous and blocking: pdfplumber parsing, the embedding call, the Claude call. FastAPI runs `def` endpoints in a threadpool and `async def` endpoints directly on the event loop, so an in-flight upload holds up every other request for its duration. `POST /query` is a plain `def` and is handled correctly.

Dropping the `async` fixes it for current traffic. The real answer is returning a job id immediately and moving ingestion to a worker, which is also what would let me show upload progress in the UI.

### Retrieval parameters are unmeasured

`k=4`, the 800-character chunks with 50-character overlap, and the router's regex patterns were chosen by inspection of real syllabi, not by measurement. I have no labeled set of documents and expected answers, so I cannot claim these are optimal, only that they behaved well on what I tested.

Two specific weaknesses I know about:

- **The router can be confidently wrong.** It falls through to semantic retrieval when a matched field is empty, but not when the match itself is bad. "What grade do I need to pass?" matches the grade-weights pattern and returns a grading breakdown, which is not the question asked. Fixing this means scoring match quality rather than treating the regex hit as binary.
- **Page citations can be off by a page.** Chunks inherit `section["start_page"]`, the page the section header appeared on. When a section spans a page break, text from the later page is still cited to the section's first page.

### Not built yet

No authentication, no rate limiting, and no file size cap on upload. Session ids are UUID4 so they are not guessable, but anyone holding one can read that session. Appropriate for a portfolio deployment, not for real users.

---

## Roadmap

1. **Build an evaluation set.** Ten syllabi with hand-labeled answers, so chunk size, `k`, and routing accuracy become measured rather than assumed. Everything below is easier to justify once this exists.
2. **Score the router instead of trusting it.** Fall through to retrieval on weak matches, not just empty fields.
3. **Move ingestion off the request path.** Job id plus a worker, which also unlocks upload progress in the UI.
4. **Fix per-chunk page tracking** so citations are exact.
