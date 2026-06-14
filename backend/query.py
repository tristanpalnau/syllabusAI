"""
query.py — Query router + RAG pipeline.

Two layers:
  Layer 1 (structured): regex match → deterministic field lookup, zero LLM calls.
  Layer 2 (RAG): embed → retrieve top-k chunks → Claude answers from context only.

The router tries Layer 1 first. If the matched field is empty in the extracted
structure (extraction missed it), it falls through to Layer 2 automatically.
"""

import os
import re
from anthropic import Anthropic
from models import SyllabusStructure
from vector_store import VectorStore


# (pattern, SyllabusStructure field name) — evaluated in order, first match wins.
# Patterns are tested against the lowercased question.
_ROUTES: list[tuple[str, str]] = [
    (r"when is (the )?(midterm|final|exam|quiz|test)",  "exam_dates"),
    (r"(due date|deadline) for",                        "assignment_deadlines"),
    (r"\boffice hours\b",                               "office_hours"),
    (r"\b(grade|worth|weight|percentage)\b",            "grade_weights"),
    (r"who is (the )?(professor|instructor|teacher)",   "instructor"),
    (r"(late|makeup).*(policy|work|assignment)",        "late_policy"),
    (r"\battendance\b",                                 "attendance_policy"),
    (r"(what (course|class)|course name)",              "course_name"),
]

_RAG_PROMPT = """\
You are a helpful assistant answering questions about a course syllabus.
Answer ONLY based on the context below. If the answer is not in the context, \
say "I don't see that information in this syllabus." Do not guess.

Context:
{context}

Question: {question}

Answer:"""


def _route(question: str) -> str | None:
    """Return the matching SyllabusStructure field name, or None to use RAG."""
    q = question.lower()
    for pattern, field in _ROUTES:
        if re.search(pattern, q):
            return field
    return None


def _format_structured(field: str, structure: SyllabusStructure) -> str | None:
    """
    Format a structured field as a readable answer.
    Returns None when the field is empty — triggers RAG fallback.
    """
    if field == "exam_dates":
        items = structure.exam_dates
        if not items:
            return None
        lines = "\n".join(f"  {e['name']}: {e['date']}" for e in items)
        return f"Scheduled exams:\n{lines}"

    if field == "assignment_deadlines":
        items = structure.assignment_deadlines
        if not items:
            return None
        lines = "\n".join(f"  {a['name']}: {a['date']}" for a in items)
        return f"Assignment deadlines:\n{lines}"

    if field == "office_hours":
        items = structure.office_hours
        if not items:
            return None
        lines = []
        for o in items:
            entry = f"  {o['instructor']}: {o['time']}"
            if o.get("location"):
                entry += f" ({o['location']})"
            lines.append(entry)
        return "Office hours:\n" + "\n".join(lines)

    if field == "grade_weights":
        weights = structure.grade_weights
        if not weights:
            return None
        lines = "\n".join(f"  {component}: {pct}%" for component, pct in weights.items())
        return f"Grading breakdown:\n{lines}"

    if field == "instructor":
        inst = structure.instructor
        if not inst:
            return None
        parts = [inst.get("name", "Unknown")]
        if inst.get("email"):
            parts.append(f"Email: {inst['email']}")
        if inst.get("office"):
            parts.append(f"Office: {inst['office']}")
        return "Instructor: " + " | ".join(parts)

    if field == "late_policy":
        return structure.late_policy  # human-readable text or None → RAG fallback

    if field == "attendance_policy":
        return structure.attendance_policy

    if field == "course_name":
        return structure.course_name

    return None


def _rag(question: str, session_id: str, store: VectorStore) -> dict:
    """Layer 2: embed question → retrieve chunks → Claude answers from context."""
    hits = store.query(session_id, question, k=4)
    if not hits:
        return {
            "answer": "I don't see that information in this syllabus.",
            "layer_used": "rag",
            "source": None,
        }

    context_parts = []
    for hit in hits:
        label = (
            f"[{hit['section_name']}, page {hit['page']}]"
            if hit.get("section_name")
            else f"[page {hit['page']}]"
        )
        context_parts.append(f"{label}\n{hit['text']}")
    context = "\n\n---\n\n".join(context_parts)

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": _RAG_PROMPT.format(context=context, question=question),
            }
        ],
    )

    pages = sorted({hit["page"] for hit in hits})
    return {
        "answer": response.content[0].text.strip(),
        "layer_used": "rag",
        "source": "page " + ", ".join(str(p) for p in pages),
    }


def answer_query(
    question: str,
    session_id: str,
    structure: SyllabusStructure,
    store: VectorStore,
) -> dict:
    """
    Route the question and return {"answer", "layer_used", "source"}.

    Tries Layer 1 first. Falls through to Layer 2 if:
      - No pattern matched, or
      - Pattern matched but the extracted field is empty (Claude missed it on upload).
    """
    field = _route(question)

    if field is not None:
        answer = _format_structured(field, structure)
        if answer is not None:
            return {
                "answer": answer,
                "layer_used": "structured",
                "source": field,
            }

    return _rag(question, session_id, store)


# ── quick smoke test when run directly ────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from ingest import ingest_pdf, extract_text_by_page
    from extract import extract_structure

    if len(sys.argv) < 2:
        print("Usage: python query.py <path_to_pdf>")
        sys.exit(1)

    load_dotenv()

    pdf_path = sys.argv[1]
    session_id = "query-smoke-test"

    print("Ingesting PDF...")
    chunks = ingest_pdf(pdf_path)
    store = VectorStore()
    store.store_chunks(session_id, chunks)
    print(f"  Stored {len(chunks)} chunks.\n")

    print("Extracting structure...")
    pages = extract_text_by_page(pdf_path)
    full_text = "\n\n".join(p["text"] for p in pages)
    structure = extract_structure(full_text)
    print(f"  Course: {structure.course_name}")
    print(f"  Exam dates found: {len(structure.exam_dates)}\n")

    test_questions = [
        "When is the final exam?",          # should hit Layer 1 (exam_dates)
        "Who is the instructor?",            # should hit Layer 1 (instructor)
        "What happens if I miss a quiz?",    # should hit Layer 2 (RAG)
    ]

    for q in test_questions:
        print(f"Q: {q}")
        result = answer_query(q, session_id, structure, store)
        print(f"   [{result['layer_used'].upper()}] source={result['source']}")
        print(f"   {result['answer']}\n")

    store.delete_session(session_id)
    print("Test session cleaned up.")
