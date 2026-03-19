"""
Prefect flow: bandi-daily-scan
Runs every day at 08:00 — scrapes all portals, deduplicates, parses, scores, notifies.

Usage:
    python -m engine.pipeline.flows          # run once immediately
    python -m engine.pipeline.flows --serve  # start scheduler (cron 08:00)
"""
from __future__ import annotations
import sys
import logging
import subprocess
from pathlib import Path
from typing import Any

from prefect import flow, task, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

# Internal imports (relative to engine/ root)
from engine.config import ARCHIVE_AFTER_DAYS

logger = logging.getLogger(__name__)

# Spider names to run on each scan
ACTIVE_SPIDERS = [
    "invitalia",
    "regione_sicilia",
    "mimit",
    "padigitale",
    "inpa",
    "comune_palermo",
    "euroinfosicilia",
]

# Path to scrapy project
SCRAPY_PROJECT_DIR = Path(__file__).parent.parent / "scrapers"


# ─────────────────────────────────────────────
# TASKS
# ─────────────────────────────────────────────

@task(name="run-spider", retries=2, retry_delay_seconds=60)
def run_spider(spider_name: str) -> dict[str, Any]:
    """Run a Scrapy spider and return summary stats."""
    task_logger = get_run_logger()
    task_logger.info(f"Starting spider: {spider_name}")

    output_file = f"/tmp/bandi_{spider_name}.jsonl"
    cmd = [
        "scrapy", "crawl", spider_name,
        "-o", output_file,
        "-s", "LOG_LEVEL=WARNING",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRAPY_PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=300,  # 5 min per spider
        )

        if result.returncode != 0:
            task_logger.error(f"Spider {spider_name} failed: {result.stderr[-500:]}")
            raise RuntimeError(f"Spider {spider_name} exited with code {result.returncode}")

        # Count lines in output
        try:
            with open(output_file) as f:
                count = sum(1 for _ in f)
        except FileNotFoundError:
            count = 0

        task_logger.info(f"Spider {spider_name}: extracted {count} items")
        return {"spider": spider_name, "count": count, "output_file": output_file, "success": True}

    except subprocess.TimeoutExpired:
        task_logger.error(f"Spider {spider_name} timed out after 5 minutes")
        return {"spider": spider_name, "count": 0, "output_file": None, "success": False, "error": "timeout"}
    except Exception as e:
        task_logger.error(f"Spider {spider_name} error: {e}")
        return {"spider": spider_name, "count": 0, "output_file": None, "success": False, "error": str(e)}


@task(name="report-spider-failures")
def report_spider_failures(results: list[dict[str, Any]]) -> None:
    """Send Telegram alert if any spiders failed."""
    task_logger = get_run_logger()
    failures = [r for r in results if not r.get("success")]

    if not failures:
        task_logger.info("All spiders completed successfully")
        return

    task_logger.warning(f"{len(failures)} spiders failed: {[f['spider'] for f in failures]}")

    try:
        from engine.notifications.alerts import send_spider_failure_alert
        for failure in failures:
            send_spider_failure_alert(
                spider_name=failure["spider"],
                error=failure.get("error", "unknown"),
            )
    except Exception as e:
        task_logger.error(f"Could not send failure alerts: {e}")


@task(name="aggregate-items")
def aggregate_items(spider_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Read JSONL files from all spiders and merge into one list."""
    import json

    task_logger = get_run_logger()
    all_items: list[dict[str, Any]] = []

    for result in spider_results:
        if not result.get("success") or not result.get("output_file"):
            continue
        try:
            with open(result["output_file"]) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            all_items.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except FileNotFoundError:
            task_logger.warning(f"Output file not found: {result['output_file']}")

    task_logger.info(f"Total items aggregated: {len(all_items)}")
    return all_items


@task(name="parse-and-score", retries=1)
def parse_and_score(item: dict[str, Any]) -> dict[str, Any]:
    """
    For a single raw scraped item:
    1. Extract structured data (Docling + Claude structurer)
    2. Return enriched item with structured fields

    Note: scoring is now per-project in evaluate_for_all_projects.
    """
    task_logger = get_run_logger()

    try:
        from engine.parsers.docling_extractor import extract_text
        from engine.parsers.claude_structurer import structure_bando

        # Extract text from PDFs if available, else use testo_html
        pdf_urls = item.get("pdf_urls", [])
        if pdf_urls:
            try:
                markdown, method = extract_text(pdf_urls[0])
            except Exception:
                markdown = item.get("testo_html", "")
        else:
            markdown = item.get("testo_html", "")

        # Structure via Claude
        structured = structure_bando(markdown, item.get("portale", ""))
        structured_dict = structured.model_dump() if hasattr(structured, "model_dump") else {}

        # Merge scraped fields with structured fields (structured wins for key fields)
        merged = {**item, **structured_dict}
        merged.setdefault("titolo", item.get("titolo", ""))
        merged.setdefault("ente_erogatore", item.get("ente_erogatore", ""))

        task_logger.info(f"Parsed: {merged.get('titolo', '')[:50]}")
        return merged

    except Exception as e:
        task_logger.error(f"parse_and_score failed for {item.get('url', 'unknown')}: {e}")
        return item


@task(name="save-to-db")
def save_to_db(items: list[dict[str, Any]]) -> dict[str, int]:
    """Save/update all items using the Scrapy pipeline logic directly."""
    task_logger = get_run_logger()
    import psycopg2
    from engine.config import DATABASE_URL
    from engine.scrapers.deduplicator import find_existing_bando, compute_dedup_hash

    inserted = 0
    updated = 0
    skipped = 0

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        for item in items:
            try:
                url = item.get("url", "")
                titolo = item.get("titolo", "")
                ente = item.get("ente_erogatore", "")

                if not url or not titolo:
                    skipped += 1
                    continue

                dedup_hash = compute_dedup_hash(ente, titolo, None)
                existing = find_existing_bando(conn, url, dedup_hash)

                if existing:
                    # State machine: update only if appropriate
                    from engine.scrapers.deduplicator import FROZEN_STATES
                    existing_stato = existing.get("stato", "")
                    if existing_stato in FROZEN_STATES:
                        skipped += 1
                        continue
                    # Silent update (never overwrite stato for existing bandi in flows)
                    cur.execute(
                        "UPDATE bandi SET data_scadenza=%s, importo_max=%s, url_fonte=COALESCE(%s, url_fonte), updated_at=NOW() WHERE id=%s",
                        (item.get("data_scadenza"), item.get("importo_max"), url, existing["id"])
                    )
                    updated += 1
                else:
                    # Insert new — objective data only (scoring is per-project)
                    from datetime import date
                    scadenza_str = item.get("data_scadenza")
                    scadenza = None
                    if scadenza_str:
                        try:
                            scadenza = date.fromisoformat(str(scadenza_str))
                        except (ValueError, TypeError):
                            pass

                    stato = "archiviato" if (scadenza and scadenza < date.today()) else "nuovo"

                    cur.execute("""
                        INSERT INTO bandi (
                            titolo, ente_erogatore, portale, url_fonte,
                            data_scadenza, importo_max, stato,
                            dedup_hash, first_seen_at, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, NOW(), NOW(), NOW()
                        )
                        ON CONFLICT (dedup_hash) DO NOTHING
                    """, (
                        titolo, ente, item.get("portale"), url,
                        scadenza, item.get("importo_max"), stato,
                        dedup_hash,
                    ))
                    inserted += 1

            except Exception as e:
                task_logger.error(f"DB error for {item.get('url')}: {e}")
                conn.rollback()

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        task_logger.error(f"DB connection failed: {e}")

    summary = {"inserted": inserted, "updated": updated, "skipped": skipped}
    task_logger.info(f"DB summary: {summary}")
    return summary


@task(name="evaluate-for-all-projects")
def evaluate_for_all_projects(items: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Evaluate all newly saved bandi against each active project.
    For each project: run hard_stops + configurable_scorer, upsert into
    project_evaluations, and send Telegram notifications for new idonei.
    """
    task_logger = get_run_logger()

    from engine.projects.manager import (
        get_active_projects, get_project, upsert_evaluation,
    )
    from engine.eligibility.rules import get_profile
    from engine.eligibility.hard_stops import check_hard_stops
    from engine.eligibility.configurable_scorer import score_bando_configurable
    from engine.notifications.alerts import send_new_bando_alert
    from engine.scrapers.deduplicator import compute_dedup_hash
    import psycopg2
    from engine.config import DATABASE_URL

    projects = get_active_projects()
    if not projects:
        task_logger.warning("No active projects — skipping evaluation")
        return {"projects": 0, "total_evaluated": 0, "total_notified": 0}

    FROZEN_EVAL_STATES = {"lavorazione", "pronto", "inviato", "archiviato"}
    total_evaluated = 0
    total_notified = 0
    project_results = {}

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        for project in projects:
            pid = project["id"]
            slug = project["slug"]
            full_project = get_project(pid)
            profile = get_profile(pid)
            scoring_rules = full_project.get("scoring_rules", {})
            evaluated = 0
            notified = 0

            for item in items:
                url = item.get("url", "")
                titolo = item.get("titolo", "")
                ente = item.get("ente_erogatore", "")

                if not url and not titolo:
                    continue

                # Find bando_id in DB
                bando_id = None
                if url:
                    cur.execute("SELECT id FROM bandi WHERE url_fonte = %s", (url,))
                    row = cur.fetchone()
                    if row:
                        bando_id = row[0]

                if not bando_id:
                    dedup_hash = compute_dedup_hash(ente, titolo, None)
                    cur.execute("SELECT id FROM bandi WHERE dedup_hash = %s", (dedup_hash,))
                    row = cur.fetchone()
                    if row:
                        bando_id = row[0]

                if not bando_id:
                    continue  # Not in DB yet (skipped by save_to_db)

                # Check if evaluation exists and is frozen
                cur.execute(
                    "SELECT stato FROM project_evaluations WHERE project_id = %s AND bando_id = %s",
                    (pid, bando_id),
                )
                existing = cur.fetchone()
                if existing and existing[0] in FROZEN_EVAL_STATES:
                    continue

                # Run hard stops
                hs_result = check_hard_stops(item, profile)
                if hs_result.excluded:
                    upsert_evaluation(
                        project_id=pid, bando_id=bando_id,
                        score=0, stato="scartato",
                        motivo_scarto=hs_result.reason,
                        hard_stop_reason=hs_result.reason,
                    )
                    evaluated += 1
                    continue

                # Run configurable scorer
                score_result = score_bando_configurable(item, profile, scoring_rules)
                stato = "scartato" if score_result.score < 40 else "idoneo"

                breakdown_dicts = [
                    {"rule": b.rule, "points": b.points, "desc": b.description, "matched": b.matched}
                    for b in score_result.breakdown
                ]

                upsert_evaluation(
                    project_id=pid, bando_id=bando_id,
                    score=score_result.score, stato=stato,
                    score_breakdown={"breakdown": breakdown_dicts},
                )
                evaluated += 1

                # Collect for notification (only brand-new idonei)
                if stato == "idoneo" and score_result.notification_worthy and not existing:
                    try:
                        send_new_bando_alert(
                            {**item, "id": bando_id, "score": score_result.score},
                            project=full_project,
                        )
                        notified += 1
                    except Exception as e:
                        task_logger.error(f"Notification failed for {slug}/{titolo[:30]}: {e}")

            project_results[slug] = {"evaluated": evaluated, "notified": notified}
            total_evaluated += evaluated
            total_notified += notified
            task_logger.info(f"Project {slug}: evaluated {evaluated}, notified {notified}")

        cur.close()
        conn.close()

    except Exception as e:
        task_logger.error(f"evaluate_for_all_projects failed: {e}")

    return {
        "projects": len(projects),
        "total_evaluated": total_evaluated,
        "total_notified": total_notified,
        "per_project": project_results,
    }


# ─────────────────────────────────────────────
# MAIN FLOW
# ─────────────────────────────────────────────

@flow(
    name="bandi-daily-scan",
    description="Daily scan of all grant portals — scrape, parse, score, notify",
    task_runner=ConcurrentTaskRunner(),
)
def daily_scan(spiders: list[str] | None = None) -> dict[str, Any]:
    """
    Main daily flow:
    1. Run all spiders in parallel
    2. Aggregate raw items
    3. Parse each item (text extraction + structuring)
    4. Save objective data to DB
    5. Evaluate against all active projects (hard stops + configurable scorer)
    6. Send Telegram notifications for new idonei per project
    7. Send progressive deadline alerts per project
    8. Weekly cleanup (Sundays) + log run to DB

    Args:
        spiders: Override list of spiders to run (default: ACTIVE_SPIDERS)
    """
    from engine.pipeline.monitor import RunMonitor

    flow_logger = get_run_logger()
    active = spiders or ACTIVE_SPIDERS
    flow_logger.info(f"Daily scan starting — {len(active)} spiders: {active}")

    with RunMonitor(spiders=active) as monitor:
        # 1. Scrape all portals in parallel
        spider_futures = [run_spider.submit(name) for name in active]
        spider_results = [f.result() for f in spider_futures]

        # 2. Report failures
        report_spider_failures(spider_results)
        spider_failures = len([r for r in spider_results if not r.get("success")])

        # 3. Aggregate
        raw_items = aggregate_items(spider_results)
        flow_logger.info(f"Aggregated {len(raw_items)} raw items")

        if not raw_items:
            flow_logger.warning("No items scraped — nothing to process")
            summary = {
                "scraped": 0, "processed": 0, "inserted": 0,
                "updated": 0, "notified": 0, "spider_failures": spider_failures,
            }
            monitor.set_result(summary)
            return summary

        # 4. Parse + score each item (concurrent)
        parse_futures = [parse_and_score.submit(item) for item in raw_items]
        enriched_items = [f.result() for f in parse_futures]

        # 5. Save to DB (objective data only)
        db_summary = save_to_db(enriched_items)

        # 6. Evaluate against all active projects + notify new idonei
        eval_result = evaluate_for_all_projects(enriched_items)
        notified = eval_result.get("total_notified", 0)

        # 7. Progressive deadline alerts per project (milestone days: 30/14/7/3/1)
        try:
            from engine.notifications.alerts import check_and_send_progressive_alerts
            from engine.projects.manager import get_active_projects as _get_projects
            for proj in _get_projects():
                check_and_send_progressive_alerts(project=proj)
        except Exception as e:
            flow_logger.error(f"Progressive alerts failed: {e}")
            monitor.add_error(f"progressive_alerts: {e}")

        # 8. Weekly cleanup (Sundays only)
        from datetime import date
        if date.today().weekday() == 6:  # Sunday = 6
            try:
                from engine.db.cleanup import run_all as run_cleanup
                cleanup_result = run_cleanup(dry_run=False)
                flow_logger.info(f"Weekly cleanup: {cleanup_result}")
            except Exception as e:
                flow_logger.error(f"Cleanup failed: {e}")
                monitor.add_error(f"cleanup: {e}")

        summary = {
            "scraped": len(raw_items),
            "processed": len(enriched_items),
            **db_summary,
            "notified": notified,
            "spider_failures": spider_failures,
        }

        monitor.set_result(summary)
        flow_logger.info(f"Daily scan complete: {summary}")

        # 9. Send scan summary via Telegram
        try:
            from engine.notifications.alerts import send_scan_summary
            send_scan_summary(summary)
        except Exception as e:
            flow_logger.error(f"Scan summary notification failed: {e}")

        return summary


# ─────────────────────────────────────────────
# ON-DEMAND RE-EVALUATION (importable by UI)
# ─────────────────────────────────────────────

FROZEN_EVAL_STATES = {"lavorazione", "pronto", "inviato", "archiviato"}


def rivaluta_singolo(pe_id: int) -> dict:
    """
    Re-evaluate a single project_evaluation by id.
    Skips if stato is frozen (lavorazione/pronto/inviato/archiviato).
    Loads soggetto profile from soggetti.profilo if soggetto_id is set,
    otherwise falls back to project profile.

    Importable directly by Django UI: from engine.pipeline.flows import rivaluta_singolo
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from engine.config import DATABASE_URL
    from engine.projects.manager import upsert_evaluation
    from engine.eligibility.rules import get_profile, get_profile_for_soggetto
    from engine.eligibility.hard_stops import check_hard_stops
    from engine.eligibility.configurable_scorer import score_bando_configurable

    with psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cur:
            # Load evaluation + bando + project data in a single query
            cur.execute("""
                SELECT
                    pe.id, pe.project_id, pe.bando_id, pe.stato, pe.soggetto_id,
                    p.scoring_rules,
                    b.titolo, b.ente_erogatore, b.tipo_finanziamento,
                    b.data_scadenza, b.importo_max, b.budget_totale,
                    b.fatturato_minimo, b.dipendenti_minimi, b.soa_richiesta,
                    b.tipo_beneficiario, b.regioni_ammesse, b.anzianita_minima_anni,
                    b.settori_ateco, b.score_breakdown, b.gap_analysis,
                    b.criteri_valutazione, b.raw_text, b.portale, b.url_fonte
                FROM project_evaluations pe
                JOIN projects p ON pe.project_id = p.id
                JOIN bandi b ON pe.bando_id = b.id
                WHERE pe.id = %s
            """, (pe_id,))
            row = cur.fetchone()

    if not row:
        return {"error": f"project_evaluation {pe_id} not found"}

    if row["stato"] in FROZEN_EVAL_STATES:
        return {"skipped": True, "reason": f"stato '{row['stato']}' è frozen", "pe_id": pe_id}

    bando = dict(row)

    # Load profile: prefer soggetto (post-migration), fallback to project
    try:
        if row["soggetto_id"]:
            profile = get_profile_for_soggetto(row["soggetto_id"])
        else:
            profile = get_profile(row["project_id"])
    except Exception:
        profile = get_profile()  # ultimate fallback: JSON singleton

    scoring_rules = row["scoring_rules"] or {}

    hs_result = check_hard_stops(bando, profile)
    if hs_result.excluded:
        upsert_evaluation(
            project_id=row["project_id"],
            bando_id=row["bando_id"],
            score=0,
            stato="scartato",
            motivo_scarto=hs_result.reason,
            hard_stop_reason=hs_result.reason,
        )
        return {"pe_id": pe_id, "stato": "scartato", "reason": hs_result.reason}

    score_result = score_bando_configurable(bando, profile, scoring_rules)
    nuovo_stato = "scartato" if score_result.score < 40 else "idoneo"
    breakdown_dicts = [
        {"rule": b.rule, "points": b.points, "desc": b.description, "matched": b.matched}
        for b in score_result.breakdown
    ]

    upsert_evaluation(
        project_id=row["project_id"],
        bando_id=row["bando_id"],
        score=score_result.score,
        stato=nuovo_stato,
        score_breakdown={"breakdown": breakdown_dicts},
    )
    return {"pe_id": pe_id, "stato": nuovo_stato, "score": score_result.score}


def rivaluta_progetto(project_id: int) -> dict:
    """
    Re-evaluate ALL non-frozen project_evaluations for a project.
    Skips frozen states (lavorazione/pronto/inviato/archiviato).

    Importable directly by Django UI: from engine.pipeline.flows import rivaluta_progetto
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from engine.config import DATABASE_URL

    with psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM project_evaluations
                WHERE project_id = %s AND stato NOT IN %s
            """, (project_id, tuple(FROZEN_EVAL_STATES)))
            pe_ids = [row["id"] for row in cur.fetchall()]

    results = {"project_id": project_id, "total": len(pe_ids), "updated": 0, "skipped": 0, "errors": 0}
    for pe_id in pe_ids:
        try:
            r = rivaluta_singolo(pe_id)
            if r.get("skipped"):
                results["skipped"] += 1
            elif "error" not in r:
                results["updated"] += 1
            else:
                results["errors"] += 1
        except Exception as e:
            logger.error(f"rivaluta_singolo({pe_id}) failed: {e}")
            results["errors"] += 1

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bandi pipeline")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--scan", action="store_true", help="Run daily scan once immediately")
    group.add_argument("--serve", action="store_true", help="Start scheduled flow (cron 08:00)")
    group.add_argument("--rivaluta", type=int, metavar="PE_ID", help="Re-evaluate a single project_evaluation by id")
    args = parser.parse_args()

    if args.serve:
        daily_scan.serve(
            name="bandi-daily-scan-scheduled",
            cron="0 8 * * *",
        )
    elif args.rivaluta:
        result = rivaluta_singolo(args.rivaluta)
        print(f"\nRivalutazione pe_id={args.rivaluta}: {result}")
    else:
        # --scan or no args: run once
        result = daily_scan()
        print(f"\nScan complete: {result}")
