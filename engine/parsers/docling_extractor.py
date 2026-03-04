"""
Document extractor using Docling (IBM).
Converts PDF/DOCX/HTML to structured markdown.
Falls back to Claude multimodal for scanned PDFs.
"""
from __future__ import annotations
import logging
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class ExtractionMethod(str, Enum):
    DOCLING   = "docling"
    CLAUDE_MM = "claude_multimodal"   # fallback for scanned PDFs
    HTML      = "html_text"           # for HTML pages


def extract_text(source: str | Path, use_claude_fallback: bool = True) -> tuple[str, ExtractionMethod]:
    """
    Extract text from a document (PDF, DOCX, or local path).

    Args:
        source: file path (str or Path) or URL
        use_claude_fallback: if True, falls back to Claude multimodal on scanned PDFs

    Returns:
        (markdown_text, method_used)
    """
    source = Path(source) if not str(source).startswith("http") else source
    is_path = isinstance(source, Path)

    if is_path and not source.exists():
        raise FileNotFoundError(f"Document not found: {source}")

    # ── Try Docling first ─────────────────────────────────────────────────────
    try:
        markdown = _extract_with_docling(source)
        if markdown and len(markdown.strip()) > 100:
            logger.info(f"Docling extracted {len(markdown)} chars from {source}")
            return markdown, ExtractionMethod.DOCLING
        else:
            logger.warning(f"Docling returned empty/short text from {source} — likely scanned PDF")
    except Exception as e:
        logger.warning(f"Docling failed on {source}: {e}")

    # ── Fallback: Claude multimodal ───────────────────────────────────────────
    if use_claude_fallback:
        try:
            markdown = _extract_with_claude_multimodal(source)
            if markdown:
                logger.info(f"Claude multimodal extracted {len(markdown)} chars from {source}")
                return markdown, ExtractionMethod.CLAUDE_MM
        except Exception as e:
            logger.error(f"Claude multimodal fallback also failed on {source}: {e}")

    raise RuntimeError(f"Could not extract text from {source} — all methods failed")


def _extract_with_docling(source) -> str:
    """Extract using Docling library."""
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()

    if isinstance(source, Path):
        result = converter.convert(str(source))
    else:
        result = converter.convert(source)  # URL

    return result.document.export_to_markdown()


def _extract_with_claude_multimodal(source) -> str:
    """
    Fallback for scanned PDFs — send as image to Claude multimodal.
    Uses base64 encoding of PDF pages.
    """
    import anthropic
    import base64

    if not isinstance(source, Path):
        raise ValueError("Claude multimodal fallback requires a local file path")

    client = anthropic.Anthropic()

    with open(source, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_data,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Estrai tutto il testo da questo documento PDF in formato markdown. "
                        "Preserva la struttura: titoli, paragrafi, tabelle, elenchi. "
                        "Non aggiungere commenti — solo il testo del documento."
                    ),
                },
            ],
        }],
    )

    return response.content[0].text
