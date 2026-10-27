"""Convert source and question PDFs to reusable Markdown files with Docling."""

from pathlib import Path


def md_path_for(pdf_path: str, content_dir: str) -> Path:
    """Return the content-directory Markdown path derived from the PDF filename."""
    pdf = Path(pdf_path)
    return Path(content_dir) / f"{pdf.stem}.md"


def convert_pdf(pdf_path: str, content_dir: str = "Content", force: bool = False) -> str:
    """Convert a PDF to Markdown and return its path, reusing an existing file unless forced."""
    out = md_path_for(pdf_path, content_dir)
    if out.exists() and not force:
        print(f"[ingest] {out} already exists, skipping (use force=True to reconvert).")
        return str(out)

    from docling.document_converter import DocumentConverter

    print(f"[ingest] converting {pdf_path} -> {out}")
    result = DocumentConverter().convert(pdf_path)
    markdown = result.document.export_to_markdown()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    return str(out)


def convert_questions_pdf(questions_pdf_path: str, content_dir: str = "Content") -> str:
    """Convert questions to content_dir/questions.md, reusing an existing Markdown file."""
    out = Path(content_dir) / "questions.md"
    if out.exists():
        print(f"[ingest] {out} already exists, skipping questions conversion.")
        return str(out)

    from docling.document_converter import DocumentConverter

    print(f"[ingest] converting questions {questions_pdf_path} -> {out}")
    result = DocumentConverter().convert(questions_pdf_path)
    markdown = result.document.export_to_markdown()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    return str(out)
