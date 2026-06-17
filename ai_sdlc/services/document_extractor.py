from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class ExtractionResult:
    combined_text: str
    sources: list[str]

    def to_markdown(self) -> str:
        source_list = "\n".join(f"- {source}" for source in self.sources)
        return f"## Sources\n\n{source_list}\n\n## Extracted Content\n\n{self.combined_text}"


def extract_uploaded_files(uploaded_files: Iterable, temp_dir: Path) -> ExtractionResult:
    chunks: list[str] = []
    sources: list[str] = []
    for uploaded in uploaded_files:
        file_path = temp_dir / uploaded.name
        file_path.write_bytes(uploaded.getvalue())
        sources.append(uploaded.name)
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            chunks.append(_extract_pdf(file_path))
        elif suffix == ".txt":
            chunks.append(file_path.read_text(encoding="utf-8", errors="ignore"))
        elif suffix in {".png", ".jpg", ".jpeg"}:
            chunks.append(_extract_image(file_path))
        else:
            chunks.append(f"Unsupported file type: {uploaded.name}")
    combined = "\n\n".join(part.strip() for part in chunks if part.strip())
    return ExtractionResult(combined or "No readable content extracted.", sources)


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        return f"PDF extraction failed for {path.name}: {exc}"


def _extract_image(path: Path) -> str:
    try:
        from PIL import Image

        image = Image.open(path)
        return f"Image uploaded: {path.name}. Size: {image.width}x{image.height}. OCR engine not configured."
    except Exception as exc:
        return f"Image extraction failed for {path.name}: {exc}"
