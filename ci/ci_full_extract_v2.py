from __future__ import annotations
import json
import sys
import traceback
from pathlib import Path

from afir_gal.config import Settings
from afir_gal.crawler import Crawler
from afir_gal.storage import Store
from afir_gal.export_xlsx import export_xlsx
from afir_gal.views import export_view_csvs
from afir_gal.quality import run_quality_checks

OUT = Path("output")
OUT.mkdir(exist_ok=True)

cfg = Settings()
config = cfg.as_dict()
config.update({
    "request_delay_seconds": 0.25,
    "timeout_seconds": 45,
    "max_retries": 4,
    "max_requests_per_run": 7000,
    "call_list_max_pages": 50,
    "closing_soon_days": 7,
})

print("=== AFIR FULL NATIONAL EXTRACTION ===", flush=True)
print(json.dumps(config, ensure_ascii=False, indent=2), flush=True)

counts = {}
crawl_error = None
crawler = Crawler(config, OUT)
try:
    counts = crawler.full_crawl(strict_national=True)
except Exception as exc:
    crawl_error = f"{type(exc).__name__}: {exc}"
    print("CRAWL ERROR:", crawl_error, file=sys.stderr, flush=True)
    traceback.print_exc()
finally:
    crawler.close()

(OUT / "crawl_counts.json").write_text(
    json.dumps(counts, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
)

store = Store(OUT / "afir_gal.db")
coverage = {}
quality_errors = 0
try:
    status_changed = store.refresh_computed_statuses(closing_soon_days=7)
    issues = run_quality_checks(store)
    quality_errors = sum(x.severity == "ERROR" for x in issues)
    quality_warnings = sum(x.severity == "WARN" for x in issues)
    store.export_csvs(OUT / "csv")
    export_view_csvs(store, OUT / "csv")
    export_xlsx(OUT / "afir_gal.db", OUT / "AFIR_GAL_Funding.xlsx", closing_soon_days=7)
    coverage = store.coverage_report()
    counts_db = {
        "gals": store.db.execute("SELECT count(*) FROM gals").fetchone()[0],
        "calls": store.db.execute("SELECT count(*) FROM calls").fetchone()[0],
        "localities": store.db.execute("SELECT count(*) FROM localities").fetchone()[0],
        "interventions": store.db.execute("SELECT count(*) FROM interventions").fetchone()[0],
        "statuses": store.db.execute("SELECT count(*) FROM call_status_history").fetchone()[0],
        "documents": store.db.execute("SELECT count(*) FROM documents").fetchone()[0],
        "raw_fields": store.db.execute("SELECT count(*) FROM raw_fields").fetchone()[0],
    }
    summary = {
        "crawl": counts,
        "crawl_error": crawl_error,
        "database_counts": counts_db,
        "status_rows_recomputed": status_changed,
        "quality_errors": quality_errors,
        "quality_warnings": quality_warnings,
        "coverage": coverage,
    }
    (OUT / "coverage_report.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (OUT / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("=== FINAL DATABASE COUNTS ===", flush=True)
    print(json.dumps(counts_db, ensure_ascii=False, indent=2), flush=True)
    print("=== COVERAGE ===", flush=True)
    print(json.dumps({k:v for k,v in coverage.items() if k not in {"per_gal", "per_gal_mismatches"}}, ensure_ascii=False, indent=2), flush=True)
    print(f"per_gal_mismatches={len(coverage.get('per_gal_mismatches', []))}", flush=True)
    print(f"quality_errors={quality_errors} quality_warnings={quality_warnings}", flush=True)
finally:
    store.close()

ok = (
    crawl_error is None
    and counts.get("coverage_gate_passed")
    and coverage.get("complete")
    and quality_errors == 0
)
if not ok:
    print("FULL EXTRACTION DID NOT RECONCILE — artifacts retained for diagnosis", file=sys.stderr, flush=True)
    sys.exit(4)
print("FULL EXTRACTION RECONCILED SUCCESSFULLY", flush=True)
