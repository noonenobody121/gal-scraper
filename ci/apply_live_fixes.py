from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else 'ci-src')

def rep(rel, old, new):
 p=root/rel; s=p.read_text()
 if old not in s: raise SystemExit(f'missing patch anchor: {rel}: {old[:60]!r}')
 p.write_text(s.replace(old,new))

def replace_between(rel, start_marker, end_marker, new):
 p=root/rel; s=p.read_text(); a=s.index(start_marker); b=s.index(end_marker,a)
 p.write_text(s[:a]+new+s[b:])

replace_between('afir_gal/manifest.py','def parse_site_manifest_html','\n\ndef validate_manifest','''def parse_site_manifest_html(html: str) -> list[SiteManifestRow]:
    """Parse AFIR national inventory using semantic card labels, with legacy fallback."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[SiteManifestRow] = []
    for card in soup.find_all(attrs={"data-gal-id": True}):
        values: dict[str, str] = {}
        for node in card.find_all(["p", "div", "span", "li"]):
            strong = node.find("strong", recursive=False)
            if strong is None: continue
            label_text = re.sub(r"\\s+", " ", strong.get_text(" ", strip=True)).strip()
            label = label_text.rstrip(":").lower()
            full = re.sub(r"\\s+", " ", node.get_text(" ", strip=True)).strip()
            value = full[len(label_text):].strip(" :") if full.startswith(label_text) else ""
            if value: values[label] = value
        cr, ar = values.get("cod autorizare"), values.get("apeluri")
        cm, am = re.search(r"\\d+", cr or ""), re.search(r"\\d+", ar or "")
        if not cm or not am: continue
        heading = card.find(["h1","h2","h3","h4","h5","h6"])
        name = re.sub(r"\\s+", " ", heading.get_text(" ", strip=True)).strip() if heading else ""
        counties = values.get("componenta teritoriala", "").replace(" ", "")
        rows.append(SiteManifestRow(int(cm.group()), name, int(am.group()), counties))
    if len(rows) >= 200:
        return sorted(rows, key=lambda r: r.authorization_code)
    lines = _clean_lines(html); fallback=[]
    for i,line in enumerate(lines):
        m=_CODE_RX.match(line)
        if not m: continue
        code=int(m.group(1)); name=lines[i-1] if i else ""; calls=None; counties=""
        for j in range(i+1,min(len(lines),i+8)):
            x=_CALL_RX.match(lines[j])
            if x and calls is None: calls=int(x.group(1)); continue
            x=_COUNTY_RX.match(lines[j])
            if x: counties=x.group(1).replace(" ",""); break
            if _CODE_RX.match(lines[j]): break
        if calls is not None: fallback.append(SiteManifestRow(code,name,calls,counties))
    return sorted(fallback,key=lambda r:r.authorization_code)
''')

replace_between('afir_gal/parsers.py','def extract_call_urls','\n\ndef extract_document_links','''def extract_call_urls(html: str, base_url: str = "https://gal.afir.ro") -> list[str]:
    """Extract only canonical AFIR call-detail links; never infer calls from arbitrary UUIDs."""
    soup = _soup(html); urls=set()
    for a in soup.find_all("a", href=True):
        href=a["href"]
        if "VizualizareApelSelectie" not in href or "idApelSelectie=" not in href: continue
        parsed=urlparse(urljoin(base_url,href)); cid=parse_qs(parsed.query).get("idApelSelectie",[None])[0]
        if cid and UUID_RE.fullmatch(cid):
            urls.add(f"{base_url.rstrip('/')}/GalApel/VizualizareApelSelectie?idApelSelectie={cid.lower()}&nrPagina=1")
    return sorted(urls)
''')
rep('afir_gal/parsers.py','''    # Best effort name: association heading first, then the text immediately after a standalone GAL label.
    name = None
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        t = clean_text(h.get_text(" ", strip=True))
        k = ascii_key(t)
        if t and "lista" not in k and "detalii" not in k and k != "gal" and len(t) > 6:
            name = t
            break
''','''    # Current AFIR header has individual Cod/Cui/Județ spans inside a parent whose title is the GAL name.
    name = None
    for tag in soup.find_all("span"):
        t = clean_text(tag.get_text(" ", strip=True))
        if not re.match(r"^Cod\\s*:\\s*\\d+", t, re.I): continue
        row = tag.parent if isinstance(tag.parent, Tag) else None
        holder = row.parent if row and isinstance(row.parent, Tag) else None
        title = clean_text(holder.get("title")) if holder and holder.get("title") else None
        if title: name=title; break
    if not name:
        for h in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
            t=clean_text(h.get_text(" ",strip=True)); k=ascii_key(t)
            if t and "lista" not in k and "detalii" not in k and "genereaza_orice_document" not in k and k != "gal" and len(t)>6:
                name=t; break
''')
rep('afir_gal/parsers.py','for label_tag in soup.find_all(["strong", "b", "label", "dt"]):','for label_tag in soup.find_all(["strong", "b", "label", "dt", "span"]):')
rep('afir_gal/parsers.py','''            if getattr(sib, "name", None) in {"strong", "b", "label", "dt"}:
                break
''','''            if getattr(sib, "name", None) in {"strong", "b", "label", "dt", "span"}:
                sib_text = clean_text(sib.get_text(" ", strip=True))
                if sib_text.endswith(":"): break
''')

rep('afir_gal/crawler.py','from .discovery import BrowserDiscovery, run\nfrom .manifest import validate_manifest\nfrom .parsers import parse_call_detail, parse_gal_detail\n','from .manifest import parse_site_manifest_html, validate_manifest\nfrom .parsers import extract_call_urls, extract_gal_urls, parse_call_detail, parse_gal_detail\n')
rep('afir_gal/crawler.py','    def _age_hours(value: str | None) -> float | None:\n','    @staticmethod\n    def _age_hours(value: str | None) -> float | None:\n')
rep('afir_gal/crawler.py','SELECT computed_status,last_seen,deadline FROM calls WHERE call_id=?','SELECT title,intervention,computed_status,last_seen,deadline FROM calls WHERE call_id=?')
rep('afir_gal/crawler.py','''        if not row:
            return True
        age = self._age_hours(row["last_seen"])
''','''        if not row:
            return True
        if not row["title"] or not row["intervention"] or (row["computed_status"] or "UNKNOWN") == "UNKNOWN":
            return True
        age = self._age_hours(row["last_seen"])
''')
insert='''    def _discover_calls_http(self, gal_id: str, expected_count: int | None = None) -> set[str]:
        urls:set[str]=set()
        if expected_count == 0: return urls
        for nr in range(1,int(self.config.get("call_list_max_pages",100))+1):
            u=(f"{self.base_url}/GalApel/ListaApeluri?galId={gal_id}&cautareApelSelectie="
               f"&nrPagina={nr}&esteRequestDeLaTriggerOnLoad=true")
            html=self._get(u,"call_list",f"{gal_id}_{nr}"); page=set(extract_call_urls(html,self.base_url)); before=len(urls); urls.update(page)
            if expected_count is not None and len(urls)>=expected_count: break
            if not page or len(urls)==before: break
        return urls

'''
rep('afir_gal/crawler.py','    def full_crawl(self, only_gal_ids: list[str] | None = None, strict_national: bool = True):\n',insert+'    def full_crawl(self, only_gal_ids: list[str] | None = None, strict_national: bool = True):\n')
start='''            browser = BrowserDiscovery(
                self.base_url,
                bool(self.config.get("browser_headless", True)),
                int(self.config.get("browser_timeout_ms", 45_000)),
                int(self.config.get("browser_settle_ms", 900)),
            )

            manifest_rows = []
            if national:
                try:
                    homepage_counters = run(browser.discover_home_counters())
                    if homepage_counters:
                        self.store.set_site_counters(homepage_counters, source_url=self.base_url + "/")
                        counts["homepage_counters"] = homepage_counters
                except Exception as exc:
                    self.store.log("WARN", f"Homepage counter capture failed: {exc}")
'''
rep('afir_gal/crawler.py',start,'            manifest_rows = []\n')
old='''            else:
                discovered = run(browser.discover_gals())
                gal_urls = sorted(discovered.urls)
                manifest_rows = discovered.manifest_rows
                for d in discovered.diagnostics:
                    self.store.log("INFO", f"GAL discovery: {d}")
                counts["manifest_gals"] = len(manifest_rows)
                counts["manifest_expected_calls"] = sum(x.expected_calls for x in manifest_rows)
                counts["manifest_validation_errors"] = validate_manifest(manifest_rows)
                if manifest_rows:
                    self.store.replace_site_manifest(manifest_rows, source_url=f"{self.base_url}/Gal/Lista?h=1")
                if not gal_urls:
                    raise RuntimeError("No GAL UUIDs discovered")
'''
new='''            else:
                manifest_url=f"{self.base_url}/Gal/Lista?h=1"; manifest_html=self._get(manifest_url,"manifest","national")
                manifest_rows=parse_site_manifest_html(manifest_html); gal_urls=sorted(extract_gal_urls(manifest_html,self.base_url))
                counts["manifest_gals"]=len(manifest_rows); counts["manifest_expected_calls"]=sum(x.expected_calls for x in manifest_rows)
                counts["manifest_validation_errors"]=validate_manifest(manifest_rows)
                self.store.log("INFO",f"GAL manifest rows={len(manifest_rows)} expected_calls={counts['manifest_expected_calls']} gal_urls={len(gal_urls)}")
                if manifest_rows: self.store.replace_site_manifest(manifest_rows,source_url=manifest_url)
                if not gal_urls: raise RuntimeError("No GAL UUIDs discovered")
'''
rep('afir_gal/crawler.py',old,new)
old='''            # Discover all call UUIDs after GAL identity has been normalized.
            call_map = run(browser.discover_calls_many(
                gal_ids,
                max_pages=int(self.config.get("call_list_max_pages", 100)),
                expected_counts=expected_by_gid,
            ))
            counts["calls_discovered"] = sum(len(x.urls) for x in call_map.values())

            for gid, disc in call_map.items():
                for d in disc.diagnostics:
                    self.store.log("INFO", f"Call discovery {gid}: {d}")
                code = gid_to_code.get(gid)
                if code is not None and code in expected_by_code:
                    expected = expected_by_code[code]
                    actual = len(disc.urls)
                    if actual != expected:
                        mismatch = {"authorization_code": code, "gal_id": gid, "expected_calls": expected, "discovered_calls": actual, "gap": expected - actual}
                        counts["call_discovery_mismatches"].append(mismatch)
                        self.store.log("ERROR", f"Call discovery mismatch code={code}: expected={expected} discovered={actual}")
'''
new='''            call_map:dict[str,set[str]]={}
            for i,gid in enumerate(gal_ids,1):
                expected=expected_by_gid.get(gid); urls=self._discover_calls_http(gid,expected); call_map[gid]=urls; code=gid_to_code.get(gid); actual=len(urls)
                if code is not None and code in expected_by_code and actual!=expected_by_code[code]:
                    ex=expected_by_code[code]; counts["call_discovery_mismatches"].append({"authorization_code":code,"gal_id":gid,"expected_calls":ex,"discovered_calls":actual,"gap":ex-actual})
                print(f"[DISCOVER {i}/{len(gal_ids)}] code={code} expected={expected} found={actual}",flush=True)
            counts["calls_discovered"]=sum(map(len,call_map.values()))
            if strict_national and counts["call_discovery_mismatches"]:
                raise RuntimeError(f"Strict national discovery mismatch for {len(counts['call_discovery_mismatches'])} GALs")
'''
rep('afir_gal/crawler.py',old,new)
rep('afir_gal/crawler.py','''                disc = call_map.get(gid)
                call_urls = sorted(disc.urls) if disc else []
''','                call_urls = sorted(call_map.get(gid, set()))\n')
rep('afir_gal/crawler.py','print(f"[GAL {i}/{len(gal_urls)}] {gal.get(\'authorization_code\')} {gal.get(\'name\')}")','print(f"[GAL {i}/{len(gal_urls)}] {gal.get(\'authorization_code\')} {gal.get(\'name\')}", flush=True)')
rep('afir_gal/crawler.py','print(f"[CALLS {i}/{len(gal_ids)}] GAL {gid} — {len(call_urls)} discovered")','print(f"[CALLS {i}/{len(gal_ids)}] GAL {gid} — {len(call_urls)} discovered", flush=True)')

rep('afir_gal/quality.py','issues.append(QualityIssue("WARN", "MISSING_CALL_TITLE"','issues.append(QualityIssue("ERROR", "MISSING_CALL_TITLE"')
rep('afir_gal/quality.py','issues.append(QualityIssue("WARN", "MISSING_INTERVENTION"','issues.append(QualityIssue("ERROR", "MISSING_INTERVENTION"')

p=root/'requirements.txt'; p.write_text('\n'.join(x for x in p.read_text().splitlines() if not x.lower().startswith('playwright'))+'\n')
p=root/'ci_full_extract.py'; p.write_text((Path(__file__).parent/'ci_full_extract_v2.py').read_text())
print('live fixes applied')
