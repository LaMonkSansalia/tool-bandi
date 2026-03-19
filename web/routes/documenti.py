"""
Documenti routes — CRUD for candidatura documents.
Uses documento_candidatura + versione_documento tables (migration 012).
Integrates with engine generators for AI document generation.
"""
import json
import threading
import uuid
from datetime import datetime
from io import BytesIO
from zipfile import ZipFile

from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, Response, StreamingResponse
from psycopg2.extras import RealDictCursor

from web.deps import get_db, get_current_project_id
from web.main import templates
from web.services.display import as_list

router = APIRouter(prefix="/candidature/{pe_id}/documenti")

CATEGORIE = [
    ("proposta_tecnica", "Proposta Tecnica"),
    ("dichiarazione", "Dichiarazione Sostitutiva"),
    ("cv_impresa", "CV Impresa"),
    ("budget", "Budget / Piano Finanziario"),
    ("preventivo", "Preventivo"),
    ("visura", "Visura Camerale"),
    ("lettera_intento", "Lettera d'Intento"),
    ("formulario", "Formulario"),
    ("altro", "Altro"),
]

STATI_DOCUMENTO = [
    ("mancante", "Mancante", "bg-gray-100 text-gray-600"),
    ("bozza", "Bozza", "bg-yellow-100 text-yellow-800"),
    ("in_revisione", "In Revisione", "bg-blue-100 text-blue-800"),
    ("approvato", "Approvato", "bg-green-100 text-green-800"),
    ("da_firmare", "Da Firmare", "bg-purple-100 text-purple-800"),
]

CATEGORIE_GENERABILI_AI = {"proposta_tecnica", "dichiarazione"}


def _check_pe_ownership(conn, pe_id: int, project_id: int) -> dict | None:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, stato, bando_id, project_id FROM project_evaluations WHERE id = %s AND project_id = %s",
            (pe_id, project_id),
        )
        return cur.fetchone()


def _table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the DB (migration may not be deployed)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
            (table_name,),
        )
        return cur.fetchone()[0]


def _get_documents(conn, pe_id: int) -> list[dict]:
    if not _table_exists(conn, "documento_candidatura"):
        return []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, nome, categoria, origine, generabile_ai, stato,
                   versione_corrente, formato_output, created_at, updated_at
            FROM documento_candidatura
            WHERE pe_id = %s
            ORDER BY
                CASE categoria
                    WHEN 'proposta_tecnica' THEN 1
                    WHEN 'dichiarazione' THEN 2
                    WHEN 'cv_impresa' THEN 3
                    WHEN 'budget' THEN 4
                    WHEN 'formulario' THEN 5
                    ELSE 9
                END,
                nome
        """, (pe_id,))
        docs = [dict(r) for r in cur.fetchall()]

    stato_map = {s[0]: (s[1], s[2]) for s in STATI_DOCUMENTO}
    cat_map = dict(CATEGORIE)
    for d in docs:
        label, css = stato_map.get(d["stato"], (d["stato"], ""))
        d["stato_label"] = label
        d["stato_css"] = css
        d["categoria_label"] = cat_map.get(d["categoria"], d["categoria"])
    return docs


@router.get("")
def documenti_list(request: Request, pe_id: int, conn=Depends(get_db)):
    """Lista documenti per una candidatura (usata come tab content HTMX)."""
    pid = get_current_project_id(request)
    pe = _check_pe_ownership(conn, pe_id, pid)
    if not pe:
        return HTMLResponse("<p>Non trovato</p>", status_code=404)

    docs = _get_documents(conn, pe_id)

    stats = {"totale": len(docs), "approvati": 0, "mancanti": 0}
    for d in docs:
        if d["stato"] == "approvato":
            stats["approvati"] += 1
        elif d["stato"] == "mancante":
            stats["mancanti"] += 1

    return templates.TemplateResponse("partials/workspace_tab_documenti_full.html", {
        "request": request,
        "pe": {"pe_id": pe_id},
        "documenti": docs,
        "stats": stats,
        "CATEGORIE": CATEGORIE,
    })


@router.post("")
def documento_create(
    request: Request,
    pe_id: int,
    nome: str = Form(""),
    categoria: str = Form("altro"),
    origine: str = Form("richiesto_bando"),
    conn=Depends(get_db),
):
    """Crea nuovo documento."""
    pid = get_current_project_id(request)
    pe = _check_pe_ownership(conn, pe_id, pid)
    if not pe:
        return RedirectResponse(url=f"/candidature/{pe_id}?tab=documenti", status_code=303)

    nome = nome.strip() or f"Documento {categoria}"
    generabile = categoria in CATEGORIE_GENERABILI_AI

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO documento_candidatura (pe_id, nome, categoria, origine, generabile_ai, stato)
            VALUES (%s, %s, %s, %s, %s, 'mancante')
        """, (pe_id, nome, categoria, origine, generabile))
        conn.commit()

    return RedirectResponse(url=f"/candidature/{pe_id}?tab=documenti", status_code=303)


@router.get("/{doc_id}")
def documento_detail(request: Request, pe_id: int, doc_id: str, conn=Depends(get_db)):
    """Dettaglio documento con editor markdown e versioni."""
    pid = get_current_project_id(request)
    pe = _check_pe_ownership(conn, pe_id, pid)
    if not pe:
        return HTMLResponse("<p>Non trovato</p>", status_code=404)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM documento_candidatura WHERE id = %s AND pe_id = %s",
            (doc_id, pe_id),
        )
        doc = cur.fetchone()

    if not doc:
        return HTMLResponse("<p>Documento non trovato</p>", status_code=404)

    doc = dict(doc)
    cat_map = dict(CATEGORIE)
    stato_map = {s[0]: (s[1], s[2]) for s in STATI_DOCUMENTO}
    doc["categoria_label"] = cat_map.get(doc["categoria"], doc["categoria"])
    label, css = stato_map.get(doc["stato"], (doc["stato"], ""))
    doc["stato_label"] = label
    doc["stato_css"] = css

    # Versioni
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, versione, autore, nota, created_at
            FROM versione_documento
            WHERE documento_id = %s
            ORDER BY versione DESC
        """, (doc_id,))
        versioni = [dict(r) for r in cur.fetchall()]

    # Bando info for context
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT b.titolo, b.ente_erogatore
            FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            WHERE pe.id = %s
        """, (pe_id,))
        bando_row = cur.fetchone()

    from web.deps import get_nav_context
    nav = get_nav_context(request, conn)

    return templates.TemplateResponse("pages/documento_editor.html", {
        "request": request,
        **nav,
        "active_page": "candidature",
        "pe_id": pe_id,
        "doc": doc,
        "versioni": versioni,
        "bando": dict(bando_row) if bando_row else {},
        "STATI_DOCUMENTO": STATI_DOCUMENTO,
    })


@router.post("/{doc_id}/salva")
def documento_save_content(
    request: Request,
    pe_id: int,
    doc_id: str,
    contenuto_markdown: str = Form(""),
    conn=Depends(get_db),
):
    """Salva contenuto markdown + crea nuova versione."""
    pid = get_current_project_id(request)
    pe = _check_pe_ownership(conn, pe_id, pid)
    if not pe:
        return RedirectResponse(url=f"/candidature/{pe_id}", status_code=303)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT versione_corrente FROM documento_candidatura WHERE id = %s AND pe_id = %s",
            (doc_id, pe_id),
        )
        row = cur.fetchone()

    if not row:
        return RedirectResponse(url=f"/candidature/{pe_id}?tab=documenti", status_code=303)

    new_version = (row["versione_corrente"] or 0) + 1

    with conn.cursor() as cur:
        # Update document
        cur.execute("""
            UPDATE documento_candidatura
            SET contenuto_markdown = %s, versione_corrente = %s,
                stato = CASE WHEN stato = 'mancante' THEN 'bozza' ELSE stato END,
                updated_at = NOW()
            WHERE id = %s
        """, (contenuto_markdown, new_version, doc_id))

        # Create version
        cur.execute("""
            INSERT INTO versione_documento (documento_id, versione, contenuto_markdown, autore, nota)
            VALUES (%s, %s, %s, 'utente', 'Salvato manualmente')
        """, (doc_id, new_version, contenuto_markdown))
        conn.commit()

    return RedirectResponse(
        url=f"/candidature/{pe_id}/documenti/{doc_id}?saved=1",
        status_code=303,
    )


@router.post("/{doc_id}/stato")
def documento_change_stato(
    request: Request,
    pe_id: int,
    doc_id: str,
    nuovo_stato: str = Form(""),
    conn=Depends(get_db),
):
    """Cambia stato documento."""
    pid = get_current_project_id(request)
    pe = _check_pe_ownership(conn, pe_id, pid)
    if not pe:
        return RedirectResponse(url=f"/candidature/{pe_id}", status_code=303)

    valid_stati = {s[0] for s in STATI_DOCUMENTO}
    if nuovo_stato not in valid_stati:
        return RedirectResponse(url=f"/candidature/{pe_id}/documenti/{doc_id}", status_code=303)

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE documento_candidatura SET stato = %s, updated_at = NOW() WHERE id = %s AND pe_id = %s",
            (nuovo_stato, doc_id, pe_id),
        )
        conn.commit()

    return RedirectResponse(url=f"/candidature/{pe_id}/documenti/{doc_id}", status_code=303)


@router.post("/{doc_id}/genera")
def documento_genera_ai(
    request: Request,
    pe_id: int,
    doc_id: str,
    istruzioni: str = Form(""),
    conn=Depends(get_db),
):
    """Genera contenuto AI in background."""
    pid = get_current_project_id(request)
    pe = _check_pe_ownership(conn, pe_id, pid)
    if not pe:
        return RedirectResponse(url=f"/candidature/{pe_id}", status_code=303)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, categoria, versione_corrente FROM documento_candidatura WHERE id = %s AND pe_id = %s",
            (doc_id, pe_id),
        )
        doc = cur.fetchone()

    if not doc:
        return RedirectResponse(url=f"/candidature/{pe_id}?tab=documenti", status_code=303)

    # Save instructions
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE documento_candidatura SET istruzioni_utente = %s, updated_at = NOW() WHERE id = %s",
            (istruzioni.strip(), doc_id),
        )
        conn.commit()

    # Launch generation in background
    def _generate(pe_id_inner, doc_id_inner, categoria, version):
        from engine.db.pool import get_conn, put_conn
        conn_bg = get_conn()
        try:
            # Load bando data
            with conn_bg.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT b.*, pe.project_id
                    FROM project_evaluations pe
                    JOIN bandi b ON pe.bando_id = b.id
                    WHERE pe.id = %s
                """, (pe_id_inner,))
                bando = cur.fetchone()

            if not bando:
                return

            bando = dict(bando)

            # Load project profile
            with conn_bg.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT profilo FROM projects WHERE id = %s",
                    (bando["project_id"],),
                )
                proj_row = cur.fetchone()

            company_profile = dict(proj_row["profilo"]) if proj_row and proj_row["profilo"] else {}

            # Generate content
            from engine.generators.content_generator import generate_content
            content = generate_content(bando, company_profile)

            # Map categoria to content field
            field_map = {
                "proposta_tecnica": content.descrizione_progetto,
                "dichiarazione": content.competenze_tecniche,
            }
            markdown = field_map.get(categoria, content.descrizione_progetto)

            new_version = (version or 0) + 1

            with conn_bg.cursor() as cur:
                cur.execute("""
                    UPDATE documento_candidatura
                    SET contenuto_markdown = %s, versione_corrente = %s,
                        stato = 'bozza', updated_at = NOW()
                    WHERE id = %s
                """, (markdown, new_version, doc_id_inner))

                cur.execute("""
                    INSERT INTO versione_documento (documento_id, versione, contenuto_markdown, autore, nota)
                    VALUES (%s, %s, %s, 'ai', 'Generato automaticamente')
                """, (doc_id_inner, new_version, markdown))
                conn_bg.commit()

        except Exception as e:
            # Log error but don't crash
            with conn_bg.cursor() as cur:
                cur.execute(
                    "UPDATE documento_candidatura SET istruzioni_utente = %s, updated_at = NOW() WHERE id = %s",
                    (f"ERRORE GENERAZIONE: {str(e)[:200]}", doc_id_inner),
                )
                conn_bg.commit()
        finally:
            put_conn(conn_bg)

    threading.Thread(
        target=_generate,
        args=(pe_id, doc_id, doc["categoria"], doc["versione_corrente"]),
        daemon=True,
    ).start()

    return RedirectResponse(
        url=f"/candidature/{pe_id}/documenti/{doc_id}?generating=1",
        status_code=303,
    )


@router.get("/{doc_id}/export/{formato}")
def documento_export(
    request: Request,
    pe_id: int,
    doc_id: str,
    formato: str,
    conn=Depends(get_db),
):
    """Export documento come PDF o DOCX."""
    pid = get_current_project_id(request)
    pe = _check_pe_ownership(conn, pe_id, pid)
    if not pe:
        return HTMLResponse("<p>Non trovato</p>", status_code=404)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM documento_candidatura WHERE id = %s AND pe_id = %s",
            (doc_id, pe_id),
        )
        doc = cur.fetchone()

    if not doc or not doc["contenuto_markdown"]:
        return HTMLResponse("<p>Nessun contenuto da esportare</p>", status_code=400)

    doc = dict(doc)

    # Load bando for context
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT b.titolo, b.ente_erogatore, p.nome AS progetto_nome, p.profilo
            FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            JOIN projects p ON pe.project_id = p.id
            WHERE pe.id = %s
        """, (pe_id,))
        ctx_row = cur.fetchone()

    context = {
        "bando": dict(ctx_row) if ctx_row else {},
        "company": dict(ctx_row["profilo"]) if ctx_row and ctx_row.get("profilo") else {},
        "content": {"descrizione_progetto": doc["contenuto_markdown"]},
        "references": [],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "version": doc["versione_corrente"],
    }

    template_name = doc["categoria"] if doc["categoria"] in ("proposta_tecnica", "dichiarazione_sostitutiva") else "proposta_tecnica"
    is_draft = doc["stato"] != "approvato"

    if formato == "pdf":
        try:
            from engine.generators.pdf_generator import generate_pdf
            pdf_bytes = generate_pdf(template_name, context, is_draft=is_draft)
            filename = f"{doc['nome']}_v{doc['versione_corrente']}.pdf"
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            return HTMLResponse(f"<p>Errore generazione PDF: {e}</p>", status_code=500)

    elif formato == "docx":
        try:
            from engine.generators.docx_generator import generate_docx
            docx_bytes = generate_docx(template_name, context)
            filename = f"{doc['nome']}_v{doc['versione_corrente']}.docx"
            return Response(
                content=docx_bytes,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as e:
            return HTMLResponse(f"<p>Errore generazione DOCX: {e}</p>", status_code=500)

    return HTMLResponse("<p>Formato non supportato</p>", status_code=400)


@router.get("/zip")
def documenti_zip(request: Request, pe_id: int, conn=Depends(get_db)):
    """Export ZIP di tutti i documenti approvati."""
    pid = get_current_project_id(request)
    pe = _check_pe_ownership(conn, pe_id, pid)
    if not pe:
        return HTMLResponse("<p>Non trovato</p>", status_code=404)

    docs = _get_documents(conn, pe_id)
    approved = [d for d in docs if d["stato"] == "approvato"]

    if not approved:
        return HTMLResponse("<p>Nessun documento approvato da esportare</p>", status_code=400)

    # Build ZIP in memory
    buf = BytesIO()
    with ZipFile(buf, "w") as zf:
        for i, doc in enumerate(approved, 1):
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT contenuto_markdown FROM documento_candidatura WHERE id = %s",
                    (doc["id"],),
                )
                row = cur.fetchone()

            if row and row["contenuto_markdown"]:
                filename = f"{i:02d}_{doc['nome']}.md"
                zf.writestr(filename, row["contenuto_markdown"])

    buf.seek(0)

    # Bando name for filename
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT b.titolo FROM project_evaluations pe
            JOIN bandi b ON pe.bando_id = b.id
            WHERE pe.id = %s
        """, (pe_id,))
        bando_row = cur.fetchone()

    bando_name = (bando_row["titolo"][:30] if bando_row else "documenti").replace(" ", "_")
    zip_filename = f"documenti_{bando_name}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
