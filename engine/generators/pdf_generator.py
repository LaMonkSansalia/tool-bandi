"""
PDF Generator — renders Jinja2 HTML templates → PDF via WeasyPrint.

Usage:
    from engine.generators.pdf_generator import generate_pdf

    pdf_bytes = generate_pdf(
        template_name="proposta_tecnica",
        context={"bando": {...}, "company": {...}, "content": {...}},
    )

    with open("output.pdf", "wb") as f:
        f.write(pdf_bytes)
"""
from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates" / "html"


def _build_jinja_env() -> Environment:
    """Build Jinja2 environment with custom filters."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )

    # Custom filter: format number with Italian separators
    def number_format(value: float | int | None) -> str:
        if value is None:
            return "⚠ DA COMPILARE"
        try:
            return f"{float(value):,.0f}".replace(",", ".")
        except (ValueError, TypeError):
            return str(value)

    env.filters["number_format"] = number_format
    return env


_env = _build_jinja_env()


def generate_pdf(
    template_name: str,
    context: dict,
    is_draft: bool = True,
    show_sources: bool = True,
) -> bytes:
    """
    Render a Jinja2 HTML template and convert to PDF via WeasyPrint.

    Args:
        template_name: Template filename without extension (e.g. "proposta_tecnica")
        context: Template variables dict
        is_draft: If True, adds BOZZA watermark
        show_sources: If True, appends sources appendix (proposta_tecnica only)

    Returns:
        PDF as bytes

    Raises:
        FileNotFoundError: If template doesn't exist
        RuntimeError: If WeasyPrint rendering fails
    """
    template_file = f"{template_name}.html"
    template_path = TEMPLATES_DIR / template_file
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    # Inject common context
    full_context = {
        "generated_at": datetime.now().strftime("%d/%m/%Y"),
        "is_draft": is_draft,
        "show_sources": show_sources,
        **context,
    }

    try:
        template = _env.get_template(template_file)
        html_content = template.render(**full_context)
    except Exception as e:
        raise RuntimeError(f"Template rendering failed: {e}") from e

    # Load base CSS
    base_css_path = TEMPLATES_DIR / "base.css"
    css = CSS(filename=str(base_css_path)) if base_css_path.exists() else None

    try:
        html_obj = HTML(
            string=html_content,
            base_url=str(TEMPLATES_DIR),
        )
        pdf_bytes = html_obj.write_pdf(stylesheets=[css] if css else None)
        logger.info(f"Generated PDF from template '{template_name}': {len(pdf_bytes)} bytes")
        return pdf_bytes
    except Exception as e:
        raise RuntimeError(f"WeasyPrint PDF generation failed: {e}") from e


def render_html(template_name: str, context: dict, is_draft: bool = True) -> str:
    """
    Render template to HTML string (for preview or debugging).
    """
    template_file = f"{template_name}.html"
    full_context = {
        "generated_at": datetime.now().strftime("%d/%m/%Y"),
        "is_draft": is_draft,
        **context,
    }
    template = _env.get_template(template_file)
    return template.render(**full_context)
