"""
ingest.py — PDF parsing + section-aware chunking pipeline

Run directly to test: python ingest.py path/to/syllabus.pdf
"""

import os
import sys
import pdfplumber


def extract_text_by_page(pdf_path: str) -> list[dict]:
    """Extract raw text from each page, preserving page numbers."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages.append({"page": page_num, "text": text.strip()})
    return pages


def _is_section_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return False
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) >= 3 and all(c.isupper() for c in letters):
        return True
    if stripped.endswith(":") and 3 < len(stripped) and len(stripped.split()) <= 8:
        return True
    # Short title-case line with no digits — e.g. "Final Grade", "Written Homework"
    if len(stripped) <= 55 and ":" not in stripped and not any(c.isdigit() for c in stripped):
        words = stripped.split()
        if 1 <= len(words) <= 6:
            significant = [w for w in words if len(w) >= 5 and w.isalpha()]
            if significant and all(w[0].isupper() for w in significant):
                return True
    return False


def detect_sections(pages: list[dict]) -> list[dict]:
    """Split document into named sections by detecting section headers."""
    lines_with_pages = []
    for page_data in pages:
        for line in page_data["text"].splitlines():
            lines_with_pages.append((line, page_data["page"]))

    sections = []
    current_name = "PREAMBLE"
    current_lines = []
    current_page = pages[0]["page"] if pages else 1

    for line, page_num in lines_with_pages:
        if _is_section_header(line):
            if current_lines:
                sections.append({
                    "name": current_name,
                    "text": "\n".join(current_lines).strip(),
                    "start_page": current_page,
                })
            current_name = line.strip().rstrip(":")
            current_lines = []
            current_page = page_num
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({
            "name": current_name,
            "text": "\n".join(current_lines).strip(),
            "start_page": current_page,
        })

    return [s for s in sections if s["text"]]


def chunk_section(
    section: dict,
    source: str,
    chunk_size: int = 800,
    overlap: int = 50,
) -> list[dict]:
    """Emit one chunk for small sections; sub-chunk large ones with overlap."""
    text = section["text"]
    name = section["name"]
    page = section["start_page"]

    if len(text) <= chunk_size:
        return [_make_chunk(text, page, 0, source, name)]

    chunks = []
    start = 0
    chunk_index = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(_make_chunk(text[start:end], page, chunk_index, source, name))
        chunk_index += 1
        if end == len(text):
            break
        start += chunk_size - overlap

    return chunks


def _make_chunk(text: str, page: int, index: int, source: str, section_name: str) -> dict:
    return {
        "text": text.strip(),
        "page": page,
        "chunk_index": index,
        "source": source,
        "section_name": section_name,
    }


def ingest_pdf(pdf_path: str) -> list[dict]:
    """Full pipeline: PDF → list of chunk dicts ready for embedding."""
    source_name = os.path.basename(pdf_path)
    pages = extract_text_by_page(pdf_path)
    sections = detect_sections(pages)

    all_chunks = []
    for section in sections:
        all_chunks.extend(chunk_section(section, source=source_name))

    return all_chunks


# ── quick smoke test when run directly ────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    chunks = ingest_pdf(pdf_path)

    print(f"\nExtracted {len(chunks)} chunks from '{pdf_path}'\n")
    for i, chunk in enumerate(chunks[:3]):
        print(f"--- Chunk {i} (page {chunk['page']}, section '{chunk['section_name']}', idx {chunk['chunk_index']}) ---")
        print(chunk["text"][:300])
        print()

    if len(chunks) > 3:
        print(f"... and {len(chunks) - 3} more chunks.")
