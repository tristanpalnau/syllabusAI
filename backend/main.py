"""
main.py — FastAPI application. Wires ingest → extract → store → query together.

Start the server:
  uvicorn main:app --reload

Endpoints:
  POST   /upload                 → { session_id, structured_summary }
  POST   /query                  → { answer, layer_used, source }
  GET    /session/{id}/structure → SyllabusStructure as JSON
  GET    /session/{id}/calendar  → .ics file download
  DELETE /session/{id}           → cleanup
"""

import dataclasses
import os
import tempfile
import uuid

from anthropic import APIError as AnthropicAPIError
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

import db
from extract import extract_structure
from ingest import extract_text_by_page, ingest_pdf
from query import answer_query
from vector_store import VectorStore

load_dotenv()

db.init_db()

app = FastAPI(title="SyllabusAI")

_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constructed once at startup: holds the ChromaDB client and the OpenAI client
# used for embeddings, for the lifetime of the process.
_store = VectorStore()


# ── request/response models ────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    session_id: str
    question: str


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """
    Accept a PDF, run the full ingest + extraction pipeline, return session_id.

    The blocking work (model inference, Claude API) runs on the async thread.
    Acceptable for a single-user portfolio app; for prod, offload to a task queue.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    contents = await file.read()
    session_id = str(uuid.uuid4())

    # pdfplumber needs a real file path, so write to a temp file then clean up.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        chunks = ingest_pdf(tmp_path)
        _store.store_chunks(session_id, chunks)

        pages = extract_text_by_page(tmp_path)
        full_text = "\n\n".join(p["text"] for p in pages)
        structure = extract_structure(full_text)
    except AnthropicAPIError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error during extraction: {e}")
    finally:
        os.unlink(tmp_path)

    db.save_session(session_id, file.filename or "", structure)

    return {
        "session_id": session_id,
        "structured_summary": dataclasses.asdict(structure),
    }


@app.post("/query")
def query(req: QueryRequest):
    structure = db.load_session(req.session_id)
    if structure is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        return answer_query(req.question, req.session_id, structure, _store)
    except AnthropicAPIError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {e}")


@app.get("/session/{session_id}/structure")
def get_structure(session_id: str):
    structure = db.load_session(session_id)
    if structure is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    return dataclasses.asdict(structure)


@app.get("/session/{session_id}/calendar")
def get_calendar(session_id: str):
    import json
    from calendar_export import generate_ics

    structure = db.load_session(session_id)
    if structure is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    result = generate_ics(structure)
    headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    if result.skipped:
        headers["X-Skipped-Events"] = json.dumps(result.skipped)
    return Response(content=result.ics_bytes, media_type="text/calendar", headers=headers)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/session/{session_id}/ping")
def ping_session(session_id: str):
    """Lets the frontend verify a session still exists after a backend restart."""
    if db.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"exists": True}


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    structure = db.load_session(session_id)
    if structure is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    _store.delete_session(session_id)
    db.delete_session(session_id)
    return {"deleted": session_id}
