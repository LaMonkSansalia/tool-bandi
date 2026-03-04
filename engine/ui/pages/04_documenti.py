"""
Pagina 04 — Documenti
Gestione documenti generati per bandi in stato 'lavorazione'.
Multi-project aware: reads from project_evaluations.
"""
import base64
import json
from datetime import datetime
from pathlib import Path

import psycopg2
import pandas as pd
import streamlit as st

from engine.config import DATABASE_URL

st.title("📄 Documenti")

pid = st.session_state.get("current_project_id", 1)

OUTPUT_BASE = Path(__file__).parent.parent.parent.parent / "output" / "bandi"


# ─────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_bandi_in_lavorazione(_pid: int):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        df = pd.read_sql("""
            SELECT b.id, b.titolo, b.ente_erogatore, pe.score, b.data_scadenza, pe.stato
            FROM bandi b
            JOIN project_evaluations pe ON pe.bando_id = b.id
            WHERE pe.project_id = %s
              AND pe.stato IN ('lavorazione', 'pronto', 'inviato')
            ORDER BY
                CASE pe.stato WHEN 'lavorazione' THEN 0 WHEN 'pronto' THEN 1 ELSE 2 END,
                pe.score DESC NULLS LAST
        """, conn, params=[_pid])
        conn.close()
        return df
    except Exception as e:
        st.error(f"Errore DB: {e}")
        return pd.DataFrame()


def load_documenti_for_bando(bando_id: int):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        df = pd.read_sql("""
            SELECT id, tipo_documento, filename, versione, stato, created_at
            FROM bando_documenti_generati
            WHERE bando_id = %s
            ORDER BY tipo_documento, versione DESC
        """, conn, params=(bando_id,))
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()


def update_documento_stato(doc_id: int, new_stato: str) -> bool:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "UPDATE bando_documenti_generati SET stato=%s WHERE id=%s",
            (new_stato, doc_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception:
        return False


def update_bando_stato(bando_id: int, new_stato: str, data_invio=None, protocollo=None) -> bool:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        if data_invio and protocollo:
            cur.execute(
                "UPDATE bandi SET stato=%s, data_invio=%s, protocollo_ricevuto=%s, updated_at=NOW() WHERE id=%s",
                (new_stato, data_invio, protocollo, bando_id)
            )
        else:
            cur.execute(
                "UPDATE bandi SET stato=%s, updated_at=NOW() WHERE id=%s",
                (new_stato, bando_id)
            )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception:
        return False


def find_package_dir(bando_id: int) -> Path | None:
    """Find the most recent output package dir for this bando."""
    if not OUTPUT_BASE.exists():
        return None
    # Load bando title for slug matching
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT titolo FROM bandi WHERE id=%s", (bando_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
    except Exception:
        return None

    # Look for submission_info.json with matching bando_id
    for d in sorted(OUTPUT_BASE.iterdir(), reverse=True):
        if d.is_dir():
            info_file = d / "submission_info.json"
            if info_file.exists():
                try:
                    info = json.loads(info_file.read_text())
                    if info.get("bando_id") == bando_id:
                        return d
                except Exception:
                    pass
    return None


# ─────────────────────────────────────────────
# MAIN UI
# ─────────────────────────────────────────────

bandi_df = load_bandi_in_lavorazione(pid)

if bandi_df.empty:
    st.info(
        "Nessun bando in lavorazione. Vai alla pagina **Bandi** e clicca "
        "'Avvia lavorazione' su un bando idoneo.",
        icon="ℹ️",
    )
    st.stop()

# Bando selector
st.subheader("Seleziona bando")

# Check if navigated here from dettaglio page
default_idx = 0
if "bando_id" in st.session_state:
    match = bandi_df[bandi_df["id"] == st.session_state["bando_id"]]
    if not match.empty:
        default_idx = int(match.index[0])

bando_options = {
    row["id"]: f"{row['titolo'][:60]} | {row['ente_erogatore']} | Score: {row['score'] or 'N/D'}"
    for _, row in bandi_df.iterrows()
}

selected_id = st.selectbox(
    "Bando",
    options=list(bando_options.keys()),
    format_func=lambda x: bando_options[x],
    index=default_idx,
)

selected_bando = bandi_df[bandi_df["id"] == selected_id].iloc[0]

# Bando header
col1, col2, col3, col4 = st.columns(4)
stato_colors = {"lavorazione": "🔵", "pronto": "🟢", "inviato": "✅"}
with col1:
    st.metric("Stato", f"{stato_colors.get(selected_bando['stato'], '⚪')} {selected_bando['stato']}")
with col2:
    st.metric("Score", f"{selected_bando['score'] or 'N/D'}/100")
with col3:
    scad = selected_bando["data_scadenza"]
    if scad:
        from datetime import date
        days_left = (pd.Timestamp(scad).date() - date.today()).days
        scad_label = f"{'🔴 ' if days_left < 14 else '🟡 ' if days_left < 30 else ''}{days_left}gg"
        st.metric("Scadenza", scad_label)
    else:
        st.metric("Scadenza", "N/D")
with col4:
    st.metric("Ente", selected_bando["ente_erogatore"][:20])

st.divider()

# ─────────────────────────────────────────────
# GENERATE PACKAGE BUTTON
# ─────────────────────────────────────────────

package_dir = find_package_dir(selected_id)

col_gen, col_zip = st.columns([2, 1])

with col_gen:
    if st.button("⚙️ Genera documenti", type="primary", help="Genera il pacchetto completo per questo bando"):
        with st.spinner("Generazione in corso... (può richiedere 1-2 minuti)"):
            try:
                from engine.generators.package_builder import build_package
                pkg_path = build_package(int(selected_id), is_draft=True)
                st.success(f"✅ Pacchetto generato: `{pkg_path}`")
                st.cache_data.clear()
                package_dir = pkg_path
            except Exception as e:
                st.error(f"❌ Errore generazione: {e}")

with col_zip:
    if package_dir and package_dir.exists():
        try:
            from engine.generators.package_builder import create_zip_package
            if st.button("📦 Scarica ZIP"):
                with st.spinner("Creazione ZIP..."):
                    zip_bytes = create_zip_package(int(selected_id))
                    titolo_slug = selected_bando["titolo"][:30].replace(" ", "_")
                    st.download_button(
                        label="⬇️ Download ZIP",
                        data=zip_bytes,
                        file_name=f"bando_{selected_id}_{titolo_slug}.zip",
                        mime="application/zip",
                    )
        except Exception as e:
            st.warning(f"ZIP non disponibile: {e}")

st.divider()

# ─────────────────────────────────────────────
# DOCUMENTS LIST
# ─────────────────────────────────────────────

st.subheader("📋 Documenti generati")
docs_df = load_documenti_for_bando(selected_id)

if docs_df.empty:
    st.info("Nessun documento generato. Clicca **Genera documenti** sopra.")
else:
    # Group by tipo_documento
    tipo_labels = {
        "proposta_tecnica": "📝 Proposta Tecnica",
        "dichiarazione_sostitutiva": "📋 Dichiarazione Sostitutiva",
        "cv_impresa": "🏢 CV Impresa",
        "allegato_a": "📎 Allegato A",
    }

    for tipo in docs_df["tipo_documento"].unique():
        tipo_docs = docs_df[docs_df["tipo_documento"] == tipo].sort_values("versione", ascending=False)
        label = tipo_labels.get(tipo, tipo)

        with st.expander(f"{label} ({len(tipo_docs)} versioni)", expanded=True):
            for _, doc in tipo_docs.iterrows():
                col_info, col_stato, col_actions = st.columns([3, 2, 3])

                with col_info:
                    stato_badge = {
                        "bozza": "🟡 Bozza",
                        "approvato": "🟢 Approvato",
                        "da_firmare": "🔏 Da firmare",
                        "firmato": "✅ Firmato",
                    }.get(doc["stato"], doc["stato"])

                    st.markdown(
                        f"**v{doc['versione']}** — {doc['filename']}\n\n"
                        f"Creato: {pd.Timestamp(doc['created_at']).strftime('%d/%m/%Y %H:%M')} | {stato_badge}"
                    )

                with col_stato:
                    new_stato = st.selectbox(
                        "Stato",
                        ["bozza", "approvato", "da_firmare", "firmato"],
                        index=["bozza", "approvato", "da_firmare", "firmato"].index(
                            doc["stato"] if doc["stato"] in ["bozza", "approvato", "da_firmare", "firmato"] else "bozza"
                        ),
                        key=f"stato_{doc['id']}",
                        label_visibility="collapsed",
                    )
                    if new_stato != doc["stato"]:
                        if update_documento_stato(int(doc["id"]), new_stato):
                            st.success("Salvato")
                            st.cache_data.clear()

                with col_actions:
                    # Find file on disk
                    if package_dir and package_dir.exists():
                        doc_file = package_dir / "documenti" / doc["filename"]
                        if doc_file.exists():
                            col_dl, col_prev = st.columns(2)
                            with col_dl:
                                file_bytes = doc_file.read_bytes()
                                mime = "application/pdf" if doc["filename"].endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                st.download_button(
                                    "⬇️ Scarica",
                                    data=file_bytes,
                                    file_name=doc["filename"],
                                    mime=mime,
                                    key=f"dl_{doc['id']}",
                                )
                            with col_prev:
                                if doc["filename"].endswith(".pdf"):
                                    if st.button("👁️ Preview", key=f"prev_{doc['id']}"):
                                        st.session_state[f"show_pdf_{doc['id']}"] = True
                        else:
                            st.caption("File non trovato su disco")
                    else:
                        st.caption("Genera prima il pacchetto")

                # PDF Preview (inline base64)
                if st.session_state.get(f"show_pdf_{doc['id']}") and package_dir:
                    doc_file = package_dir / "documenti" / doc["filename"]
                    if doc_file.exists() and doc["filename"].endswith(".pdf"):
                        b64 = base64.b64encode(doc_file.read_bytes()).decode()
                        st.markdown(
                            f'<iframe src="data:application/pdf;base64,{b64}" '
                            f'width="100%" height="600px" type="application/pdf"></iframe>',
                            unsafe_allow_html=True,
                        )
                        if st.button("Chiudi preview", key=f"close_prev_{doc['id']}"):
                            st.session_state[f"show_pdf_{doc['id']}"] = False
                            st.rerun()

                st.markdown("---")

st.divider()

# ─────────────────────────────────────────────
# PACKAGE FILES (if exists)
# ─────────────────────────────────────────────

if package_dir and package_dir.exists():
    with st.expander("📁 File nel pacchetto", expanded=False):
        for f in sorted(package_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(package_dir)
                size_kb = f.stat().st_size / 1024
                st.markdown(f"`{rel}` — {size_kb:.1f} KB")

    # Show checklist
    checklist_file = package_dir / "01_checklist_invio.md"
    if checklist_file.exists():
        with st.expander("✅ Checklist invio", expanded=False):
            st.markdown(checklist_file.read_text(encoding="utf-8"))

    # Show submission info
    info_file = package_dir / "submission_info.json"
    if info_file.exists():
        with st.expander("📋 Informazioni invio (submission_info.json)", expanded=False):
            info = json.loads(info_file.read_text())
            st.json(info)

st.divider()

# ─────────────────────────────────────────────
# SUBMISSION TRACKING
# ─────────────────────────────────────────────

st.subheader("📮 Registra invio")

if selected_bando["stato"] != "inviato":
    with st.form("invio_form"):
        st.markdown("Una volta inviata la domanda, registra qui i dati di invio:")
        col1, col2 = st.columns(2)
        with col1:
            data_invio = st.date_input("Data invio", value=datetime.today())
        with col2:
            protocollo = st.text_input("Numero protocollo ricevuto", placeholder="es. PROT/2026/12345")

        submitted = st.form_submit_button("✅ Segna come Inviato", type="primary")
        if submitted:
            if not protocollo:
                st.warning("Inserire il numero di protocollo")
            else:
                ok = update_bando_stato(
                    int(selected_id),
                    "inviato",
                    data_invio=data_invio,
                    protocollo=protocollo,
                )
                if ok:
                    # Update submission_info.json
                    if package_dir and info_file.exists():
                        info = json.loads(info_file.read_text())
                        info["data_invio"] = data_invio.isoformat()
                        info["protocollo_ricevuto"] = protocollo
                        info_file.write_text(json.dumps(info, indent=2, ensure_ascii=False))

                    # Send Telegram notification
                    try:
                        from engine.notifications.alerts import _send_message
                        _send_message(
                            f"✅ *Domanda inviata!*\n\n"
                            f"Bando: *{selected_bando['titolo'][:60]}*\n"
                            f"Data: {data_invio.strftime('%d/%m/%Y')}\n"
                            f"Protocollo: `{protocollo}`"
                        )
                    except Exception:
                        pass

                    st.success(f"✅ Bando marcato come inviato! Protocollo: {protocollo}")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Errore aggiornamento DB")
else:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT data_invio, protocollo_ricevuto FROM bandi WHERE id=%s",
            (selected_id,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0]:
            st.success(
                f"✅ **Domanda già inviata**\n\n"
                f"- Data invio: {row[0].strftime('%d/%m/%Y')}\n"
                f"- Protocollo: {row[1] or 'N/D'}"
            )
    except Exception:
        st.info("Domanda già segnata come inviata.")
