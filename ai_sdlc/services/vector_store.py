from __future__ import annotations

from pathlib import Path


class VectorStoreService:
    def __init__(self, persist_directory: Path):
        self.persist_directory = persist_directory
        self.persist_directory.mkdir(parents=True, exist_ok=True)

    def store_text(self, text: str, sources: list[str]) -> str:
        chunks = self._chunk(text)
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(self.persist_directory))
            collection = client.get_or_create_collection("ai_sdlc_documents")
            if chunks:
                collection.add(
                    ids=[f"chunk-{index}" for index, _ in enumerate(chunks)],
                    documents=chunks,
                    metadatas=[{"source": ", ".join(sources)} for _ in chunks],
                )
            return f"Stored {len(chunks)} chunks in ChromaDB at {self.persist_directory}."
        except Exception as exc:
            fallback = self.persist_directory / "document_chunks.txt"
            fallback.write_text("\n\n---CHUNK---\n\n".join(chunks), encoding="utf-8")
            return f"ChromaDB unavailable; stored {len(chunks)} chunks as text fallback at {fallback}. Reason: {exc}"

    def _chunk(self, text: str, size: int = 1200, overlap: int = 150) -> list[str]:
        clean = text.strip()
        if not clean:
            return []
        chunks = []
        start = 0
        while start < len(clean):
            end = min(start + size, len(clean))
            chunks.append(clean[start:end])
            if end == len(clean):
                break
            start = max(end - overlap, start + 1)
        return chunks
