from __future__ import annotations

from io import BytesIO


def markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48)
        styles = getSampleStyleSheet()
        story = []
        for raw_line in markdown_text.splitlines():
            line = raw_line.strip()
            if not line:
                story.append(Spacer(1, 8))
                continue
            if line.startswith("# "):
                story.append(Paragraph(_escape(line[2:]), styles["Title"]))
            elif line.startswith("## "):
                story.append(Paragraph(_escape(line[3:]), styles["Heading2"]))
            elif line.startswith("- "):
                story.append(Paragraph(f"&bull; {_escape(line[2:])}", styles["BodyText"]))
            else:
                story.append(Paragraph(_escape(line), styles["BodyText"]))
        doc.build(story)
        return buffer.getvalue()
    except Exception:
        return _minimal_pdf(markdown_text)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _minimal_pdf(text: str) -> bytes:
    lines = ["AI SDLC Platform Report", *text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").splitlines()]
    visible_lines = [line[:95] for line in lines[:42]]
    commands = ["BT", "/F1 10 Tf", "50 760 Td"]
    for index, line in enumerate(visible_lines):
        if index:
            commands.append("0 -16 Td")
        commands.append(f"({line}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj\n",
    ]
    pdf = BytesIO()
    pdf.write(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(pdf.tell())
        pdf.write(obj)
    xref = pdf.tell()
    pdf.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        pdf.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.write(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii"))
    return pdf.getvalue()
