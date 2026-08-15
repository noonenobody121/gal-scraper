from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else 'ci-src')/'afir_gal'

def replace(rel,old,new,count=1):
 p=root/rel; s=p.read_text()
 if old not in s: raise SystemExit(f'missing patch anchor {rel}: {old[:80]!r}')
 p.write_text(s.replace(old,new,count))

# Call pages use direct sibling spans. Capture them structurally so values that
# themselves end in ':' (valid AFIR call titles) are not mistaken for labels.
replace('parsers.py','''    candidates = []\n    for tag in soup.find_all(["p", "div", "span", "td", "li"]):\n''','''    candidates = []\n    for group in soup.find_all(["div", "p", "li", "td"]):\n        spans = group.find_all("span", recursive=False)\n        if len(spans) < 2:\n            continue\n        label_text = clean_text(spans[0].get_text(" ", strip=True))\n        if not label_text.endswith(":"):\n            continue\n        value_text = clean_text(" ".join(x.get_text(" ", strip=True) for x in spans[1:]))\n        if value_text:\n            candidates.append(f"{label_text} {value_text}")\n    for tag in soup.find_all(["p", "div", "span", "td", "li"]):\n''')

# AFIR contains one cancelled call whose source timestamps have launch after deadline.
# Preserve source data and flag it as a warning instead of fabricating a correction.
replace('quality.py','''                if datetime.fromisoformat(launch) > datetime.fromisoformat(deadline):\n                    issues.append(QualityIssue("ERROR", "DATE_ORDER", "call", cid, "Launch is after deadline"))\n''','''                if datetime.fromisoformat(launch) > datetime.fromisoformat(deadline):\n                    if "anulat" in (row.get("site_running_raw") or "").lower():\n                        issues.append(QualityIssue("WARN", "SOURCE_DATE_ORDER_ANOMALY", "call", cid,\n                                                   "AFIR source marks the call ANULAT and stores launch after deadline; source values preserved"))\n                    else:\n                        issues.append(QualityIssue("ERROR", "DATE_ORDER", "call", cid, "Launch is after deadline"))\n''')

p=root/'locality.py'; s=p.read_text(); a=s.index('def _norm_name('); b=s.index('\n\ndef _norm_county',a)
new='''def _norm_name(text: str | None) -> str:\n    s = clean_text(text or "").casefold()\n    s = s.replace("ş", "ș").replace("ţ", "ț").replace("â", "î").replace("ã", "a")\n    s = unicodedata.normalize("NFKD", s)\n    s = "".join(ch for ch in s if not unicodedata.combining(ch))\n    s = re.sub(r"[^a-z0-9]+", " ", s)\n    s = re.sub(r"\\b(municipiul|municipiu|orasul|oras|comuna|satul|sat)\\b", " ", s)\n    return re.sub(r"\\s+", " ", s).strip()\n'''
s=s[:a]+new+s[b:]
s=s.replace('''            # We care about locality/UAT records; county rows are only hierarchy metadata.\n            if level == "1":\n                continue\n''','''            # AFIR territory entries are UATs; official SIRUTA NIV=2 is the safe matching layer.\n            if level and level != "2":\n                continue\n''',1).replace('if score >= 0.94:','if score >= 0.92:',1)
p.write_text(s)

# Expose both the exact resolved county and the GAL's published county scope.
replace('export_xlsx.py','''        SELECT l.locality,\n               CASE WHEN lr.county IS NOT NULL THEN lr.county\n''','''        SELECT l.locality,\n               (SELECT group_concat(county, ',') FROM gal_counties gc WHERE gc.gal_id=l.gal_id) AS gal_counties,\n               CASE WHEN lr.county IS NOT NULL THEN lr.county\n''',2)
replace('export_xlsx.py','''               lr.siruta_code,lr.uat_name,\n               g.name AS gal_name,g.authorization_code,\n''','''               lr.siruta_code,lr.uat_name,\n               COALESCE(lr.status,CASE WHEN (SELECT count(*) FROM gal_counties z WHERE z.gal_id=l.gal_id)=1 THEN 'COUNTY_ONLY' ELSE 'UNRESOLVED' END) AS locality_resolution_status,\n               g.name AS gal_name,g.authorization_code,\n''')
replace('export_xlsx.py','''        SELECT l.gal_id,g.name AS gal_name,l.locality,lr.county,lr.siruta_code,lr.uat_name,lr.status,lr.confidence,lr.method,lr.source_ref\n''','''        SELECT l.gal_id,g.name AS gal_name,(SELECT group_concat(county, ',') FROM gal_counties gc WHERE gc.gal_id=l.gal_id) AS gal_counties,\n               l.locality,lr.county,lr.siruta_code,lr.uat_name,lr.status,lr.confidence,lr.method,lr.source_ref\n''')

replace('views.py','''                l.locality,\n                CASE\n''','''                l.locality,\n                (SELECT group_concat(county, ',') FROM gal_counties gc WHERE gc.gal_id=l.gal_id) AS gal_counties,\n                CASE\n''')
replace('views.py','''                    l.locality,\n                    CASE\n''','''                    l.locality,\n                    (SELECT group_concat(county, ',') FROM gal_counties gc WHERE gc.gal_id=l.gal_id) AS gal_counties,\n                    CASE\n''')
replace('views.py','''                    END AS county,\n                    g.name AS gal_name,\n''','''                    END AS county,\n                    lr.siruta_code,lr.uat_name,\n                    COALESCE(lr.status, CASE WHEN (SELECT count(*) FROM gal_counties z WHERE z.gal_id=l.gal_id)=1 THEN 'COUNTY_ONLY' ELSE 'UNRESOLVED' END) AS locality_resolution_status,\n                    g.name AS gal_name,g.authorization_code,\n''')
print('final fixes applied')
