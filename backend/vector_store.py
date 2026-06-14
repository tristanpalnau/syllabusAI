"""
vector_store.py — ChromaDB wrapper for per-session chunk storage + retrieval

Run directly to test: python vector_store.py path/to/syllabus.pdf
"""

import os
import sys
import chromadb
from openai import OpenAI

_EMBED_MODEL = "text-embedding-3-small"


def _embed(client: OpenAI, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=_EMBED_MODEL, input=texts)
    return [e.embedding for e in response.data]


class VectorStore:
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def store_chunks(self, session_id: str, chunks: list[dict]) -> None:
        """Embed chunks and store them in a session-scoped ChromaDB collection."""
        collection = self.client.get_or_create_collection(f"session_{session_id}")

        texts = [c["text"] for c in chunks]
        embeddings = _embed(self.openai, texts)
        ids = [f"{session_id}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "page": c["page"],
                "source": c["source"],
                "chunk_index": c["chunk_index"],
                "section_name": c.get("section_name", ""),
            }
            for c in chunks
        ]

        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    def query(self, session_id: str, question: str, k: int = 4) -> list[dict]:
        """
        Find the top-k chunks most semantically similar to the question.
        Returns list of {text, page, source, chunk_index, distance}.
        """
        collection = self.client.get_collection(f"session_{session_id}")
        query_embedding = _embed(self.openai, [question])

        results = collection.query(query_embeddings=query_embedding, n_results=k)

        hits = []
        for text, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append(
                {
                    "text": text,
                    "page": meta["page"],
                    "source": meta["source"],
                    "chunk_index": meta["chunk_index"],
                    "section_name": meta.get("section_name", ""),
                    "distance": dist,
                }
            )
        return hits

    def delete_session(self, session_id: str) -> None:
        """Remove a session's collection (call on DELETE /session/{id})."""
        self.client.delete_collection(f"session_{session_id}")


# ── quick smoke test when run directly ────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vector_store.py <path_to_pdf>")
        sys.exit(1)

    from ingest import ingest_pdf

    pdf_path = sys.argv[1]
    chunks = ingest_pdf(pdf_path)
    print(f"Ingested {len(chunks)} chunks.")

    store = VectorStore()
    session_id = "test-session"

    print("Storing chunks (embedding via OpenAI API)...")
    store.store_chunks(session_id, chunks)
    print("Stored.\n")

    question = "What is the late policy?"
    print(f"Query: '{question}'")
    hits = store.query(session_id, question)
    for hit in hits:
        print(f"\n  [page {hit['page']}, dist={hit['distance']:.4f}]")
        print(f"  {hit['text'][:300]}")

    store.delete_session(session_id)
    print("\nTest session cleaned up.")
