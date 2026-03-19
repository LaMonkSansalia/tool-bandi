# Prompt per Claude Code — Analisi Repo e Match con Nuova UI

## Contesto

Sto riprogettando la UI di Tool Bandi, un'applicazione per gestire bandi pubblici italiani. Ho una nuova specifica UI/UX completa (`tool-bandi-spec.md`) e un mockup React navigabile (`tool-bandi-mockup.jsx`) che definiscono l'architettura target.

L'applicazione ha un backend Python già esistente in questo repo che:
- Scrapa 7 portali governativi italiani per trovare bandi
- Analizza i PDF dei bandi con AI (Docling + Claude)
- Valuta automaticamente idoneità e punteggio
- Genera documenti per la candidatura

## Cosa devi fare

### Step 1 — Analisi del repo esistente

Esplora l'intero repo e mappami:

1. **Struttura del progetto**: cartelle, moduli principali, entry points
2. **Modello dati attuale**: quali entità esistono nel DB? Come sono le tabelle? Qual è lo schema? Confronta con il modello dati nella spec (`tool-bandi-spec.md`, sezione 2) e dimmi:
   - Cosa esiste già e corrisponde
   - Cosa esiste ma va modificato
   - Cosa manca e va creato da zero
3. **API endpoints esistenti**: lista tutti gli endpoint REST, cosa fanno, cosa accettano e ritornano
4. **Pipeline di scraping**: come funziona lo scraping? Quali portali? Come viene triggerato?
5. **Analisi PDF**: come funziona l'estrazione testo? Quali librerie usa? Come vengono estratti criteri e requisiti?
6. **Sistema di valutazione**: come funziona lo scoring? Come vengono calcolati hard stop e idoneità? Dove sono le scoring rules?

### Step 2 — Focus su generazione documenti

Questa è la parte più critica da capire. Analizza in dettaglio:

1. **Esiste un sistema di generazione documenti?** Se sì:
   - Quali tipi di documenti può generare? (proposta tecnica, dichiarazioni, CV impresa, budget, altro?)
   - Come funziona? (prompt a Claude? Template? Mix?)
   - Quali dati usa come input? (dati progetto, soggetto, bando?)
   - In che formato genera? (PDF, DOCX, Markdown, HTML?)
   - C'è versioning dei documenti generati?

2. **Se non esiste ancora**, analizza:
   - Ci sono stub, placeholder, o TODO relativi alla generazione documenti?
   - Quali dati sono disponibili nel sistema che potrebbero alimentare la generazione?
   - Qual è il modo più naturale di integrare la generazione documenti nell'architettura esistente?

3. **Estrazione requisiti documentali dal bando**: il sistema quando analizza il PDF di un bando, estrae anche la lista dei documenti richiesti per la candidatura? (es: "servono: proposta tecnica, DSAN, preventivi, visura camerale")

### Step 3 — Gap Analysis Backend vs Nuova UI

Usando la spec `tool-bandi-spec.md` come riferimento, dimmi per ogni pagina/funzionalità:

| Funzionalità UI | Endpoint/logica backend necessaria | Stato (esiste/parziale/manca) | Note |
|---|---|---|---|
| Dashboard - stat cards | ... | ... | ... |
| Dashboard - candidature urgenti | ... | ... | ... |
| Lista soggetti | ... | ... | ... |
| Dettaglio soggetto - hard stops | ... | ... | ... |
| Lista progetti raggruppata | ... | ... | ... |
| Progetto - tab Opportunità | ... | ... | ... |
| Progetto - tab Candidature | ... | ... | ... |
| Lista bandi con filtro progetto | ... | ... | ... |
| Bando - decisione rapida (pro/contro) | ... | ... | ... |
| Creazione candidatura | ... | ... | ... |
| Workspace - valutazione read-only | ... | ... | ... |
| Workspace - genera documenti | ... | ... | ... |
| Workspace - checklist | ... | ... | ... |
| Workspace - note e invio | ... | ... | ... |
| Pipeline - avvio scansione | ... | ... | ... |

### Step 4 — Proposta di integrazione documenti

Basandoti su quello che hai trovato nel repo, proponi:

1. **Quali documenti il sistema può/dovrebbe generare automaticamente** e come (prompt Claude, template, mix)
2. **Schema dati per i documenti** nella candidatura:
   ```
   documento = {
     id, candidatura_id,
     tipo: "generato_ai" | "upload_manuale",
     categoria: "proposta_tecnica" | "dichiarazione" | "cv_impresa" | "budget" | "preventivo" | "visura" | "lettera_intento" | "formulario" | "altro",
     nome, descrizione,
     versione: int,
     stato: "bozza" | "in_revisione" | "approvato" | "da_firmare",
     contenuto: text (per documenti generati, contenuto editabile),
     file_path: string (per upload o PDF generato),
     formato: "markdown" | "pdf" | "docx",
     generato_da: "ai" | "utente" | "sistema",
     prompt_usato: text (se generato AI, per rigenerazione),
     created_at, updated_at
   }
   ```
3. **Flusso UI proposto per i documenti** nel workspace candidatura:
   - Lista documenti richiesti (estratti dal bando + default)
   - Per ogni documento: stato, azione possibile (genera / carica / modifica / approva)
   - Editor inline per documenti generati (markdown → preview)
   - Upload per documenti manuali
   - Versioning (ogni modifica o rigenerazione crea nuova versione)
   - Export: singolo PDF, pacchetto ZIP completo

4. **Endpoint API necessari** per i documenti:
   - POST /candidature/{id}/documenti/genera — genera un documento AI
   - PUT /candidature/{id}/documenti/{doc_id} — modifica contenuto
   - POST /candidature/{id}/documenti/upload — upload manuale
   - GET /candidature/{id}/documenti/{doc_id}/preview — anteprima
   - GET /candidature/{id}/documenti/export-zip — pacchetto completo

## File di riferimento

I due file che definiscono la UI target sono:
- `tool-bandi-spec.md` — specifica completa (modello dati, pagine, flussi, stati)
- `tool-bandi-mockup.jsx` — mockup React navigabile con dati mock

Leggili entrambi per intero prima di iniziare l'analisi del repo.

## Output atteso

Dammi un report strutturato con le 4 sezioni sopra. Sii specifico: nomi di file, funzioni, classi, tabelle DB, endpoint. Non generalizzare — voglio sapere esattamente cosa c'è e cosa manca.

Per la sezione documenti, proponi un'implementazione concreta che si integri con l'architettura esistente del repo, non una soluzione generica.
