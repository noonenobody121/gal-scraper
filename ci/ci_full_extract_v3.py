from __future__ import annotations
import json, sys, traceback
from collections import Counter
from pathlib import Path
from afir_gal.config import Settings
from afir_gal.crawler import Crawler
from afir_gal.storage import Store
from afir_gal.export_xlsx import export_xlsx
from afir_gal.views import export_view_csvs
from afir_gal.quality import run_quality_checks
from afir_gal.locality import SirutaGazetteer

OUT=Path('output'); OUT.mkdir(exist_ok=True)
config=Settings().as_dict(); config.update(request_delay_seconds=.25,timeout_seconds=45,max_retries=4,max_requests_per_run=7000,call_list_max_pages=50,closing_soon_days=7)
print('=== AFIR FULL NATIONAL EXTRACTION V4 / CLEAN INTERVENTIONS ===',flush=True)
crawl_error=None; counts={}
crawler=Crawler(config,OUT)
try: counts=crawler.full_crawl(strict_national=True)
except Exception as exc:
    crawl_error=f'{type(exc).__name__}: {exc}'; print('CRAWL ERROR',crawl_error,file=sys.stderr,flush=True); traceback.print_exc()
finally: crawler.close()
(OUT/'crawl_counts.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

store=Store(OUT/'afir_gal.db')
try:
    locality_counts={}
    if Path('siruta.csv').exists():
        locality_counts=store.resolve_localities(SirutaGazetteer.from_csv('siruta.csv'),source_ref='sirutalib 1.3.0 maintained SIRUTA mirror; official data.gov.ro source documented')
    store.refresh_computed_statuses(closing_soon_days=7)
    issues=run_quality_checks(store); errors=[x for x in issues if x.severity=='ERROR']; warns=[x for x in issues if x.severity=='WARN']

    core_call_fields=[
        'title','intervention','financing_type_raw','launch','deadline','site_running_raw','description',
        'submission_ceiling_eur','allocated_funds_eur','available_funds_raw','submitted_value_eur',
        'max_grant_eur','min_score','support_rate_pct','projects_submitted','projects_withdrawn'
    ]
    missing_core={}
    for col in core_call_fields:
        row=store.db.execute(
            f"SELECT count(*) FROM calls WHERE {col} IS NULL OR (typeof({col})='text' AND trim({col})='')"
        ).fetchone()
        missing_core[col]=row[0]

    intervention_integrity={
        'total': store.db.execute('SELECT count(*) FROM interventions').fetchone()[0],
        'uncoded': store.db.execute("SELECT count(*) FROM interventions WHERE code IS NULL OR trim(code)='' ").fetchone()[0],
        'footer_or_navigation_noise': store.db.execute(
            "SELECT count(*) FROM interventions WHERE lower(coalesce(name,'')) LIKE '%urmăriți-ne pe%' "
            "OR lower(coalesce(name,'')) LIKE '%urmariti-ne pe%' "
            "OR lower(coalesce(name,'')) LIKE '%lansată în data de%' "
            "OR lower(coalesce(name,'')) LIKE '%lansata in data de%'"
        ).fetchone()[0],
        'distinct_gals': store.db.execute('SELECT count(DISTINCT gal_id) FROM interventions').fetchone()[0],
    }

    store.export_csvs(OUT/'csv'); export_view_csvs(store,OUT/'csv')
    coverage=store.coverage_report()
    db_counts={k:store.db.execute(q).fetchone()[0] for k,q in {
      'gals':'SELECT count(*) FROM gals','calls':'SELECT count(*) FROM calls','localities':'SELECT count(*) FROM localities',
      'interventions':'SELECT count(*) FROM interventions','statuses':'SELECT count(*) FROM call_status_history',
      'raw_fields':'SELECT count(*) FROM raw_fields'}.items()}
    summary={
        'crawl':counts,'crawl_error':crawl_error,'database_counts':db_counts,
        'core_call_missing':missing_core,'intervention_integrity':intervention_integrity,
        'locality_resolution':locality_counts,'quality_errors':len(errors),'quality_warnings':len(warns),
        'error_codes':dict(Counter(x.code for x in errors)),'warning_codes':dict(Counter(x.code for x in warns)),
        'coverage':coverage
    }
    (OUT/'coverage_report.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    (OUT/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
finally: store.close()

export_xlsx(OUT/'afir_gal.db',OUT/'AFIR_GAL_Funding.xlsx',closing_soon_days=7)
print(json.dumps(summary,ensure_ascii=False,indent=2,default=str),flush=True)

core_complete=all(v==0 for v in missing_core.values())
interventions_clean=(intervention_integrity['uncoded']==0 and intervention_integrity['footer_or_navigation_noise']==0)
ok=(crawl_error is None and counts.get('coverage_gate_passed') and coverage.get('complete') and len(errors)==0 and core_complete and interventions_clean)
if not ok:
    print('FULL EXTRACTION FAILED STRICT QUALITY/COVERAGE/SCHEMA GATE',file=sys.stderr,flush=True); sys.exit(4)
print('FULL EXTRACTION RECONCILED: coverage complete; core fields complete; interventions clean; zero quality errors',flush=True)
