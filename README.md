# AFIR GAL national public-data extractor

Production-oriented extractor and reconciliation workflow for the public GAL funding data at `gal.afir.ro`.

## Current national contract

A successful full run must derive the manifest from the same live AFIR snapshot and then satisfy all of these conditions:

- every GAL authorization code in the national manifest has a GAL detail row;
- every GAL's extracted unique call count equals the `Apeluri` count published for that GAL;
- total extracted calls equals the sum of the same-run per-GAL manifest counts;
- no GAL/call fetch failures;
- no required-field QA errors;
- duplicate call IDs are impossible in the canonical SQLite store.

The validated August 2026 snapshot contains **246 GALs and 1,702 public selection calls**. Do not hard-code these figures for future runs: the workflow reads the current national manifest every time.

## Outputs

The `AFIR full national extraction` GitHub Actions workflow uploads:

- `AFIR_GAL_Funding.xlsx` — browsing workbook;
- `afir_gal.db` — canonical normalized SQLite database;
- `csv/` — relational and convenience CSV exports;
- `coverage_report.json` — national GAL/call reconciliation;
- `run_summary.json` and `crawl_counts.json` — runtime/QA metrics;
- raw HTML snapshots for GAL, call-list, and call-detail pages;
- workflow log.

Important workbook views include `AvailableNow`, `Opportunities`, `ByLocality`, `GALs`, `Localities`, `Interventions`, `Statuses`, `Quality`, `CoverageAudit`, and `RawFields`.

## Locality/county semantics

AFIR publishes GAL county scope plus a flat list of territory locality names. The extractor resolves locality names against SIRUTA at the UAT level where the public data permits a unique mapping.

- `county`: exact resolved county where determinable;
- `gal_counties`: all counties AFIR publishes for the GAL;
- `locality_resolution_status`: `MATCHED`, `MATCHED_FUZZY`, `COUNTY_ONLY`, or `AMBIGUOUS`.

An `AMBIGUOUS` row is intentionally **not guessed** when the same UAT name exists in multiple counties covered by that GAL and AFIR does not provide a locality-to-county key.

## Acquisition

Call discovery uses AFIR's own rendered/HTMX list output and extracts canonical `VizualizareApelSelectie?idApelSelectie=...` links only. It does not infer calls from arbitrary UUIDs in the page.

The `/Proiect/...` application routes unauthenticated users to AFIR login. Authenticated project records are therefore not treated as public crawlable data by this repository.

## Run

Use **Actions → AFIR full national extraction → Run workflow** or push a change to the production workflow/source paths.

The workflow exits non-zero if national coverage or required-field QA does not reconcile, while still retaining diagnostic artifacts.
