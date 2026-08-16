from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'ci-src') / 'afir_gal'


def replace_between(rel: str, start_marker: str, end_marker: str, new: str) -> None:
    p = root / rel
    s = p.read_text()
    a = s.index(start_marker)
    b = s.index(end_marker, a)
    p.write_text(s[:a] + new + s[b:])


def insert_before(rel: str, marker: str, new: str) -> None:
    p = root / rel
    s = p.read_text()
    if marker not in s:
        raise SystemExit(f'missing patch anchor {rel}: {marker!r}')
    p.write_text(s.replace(marker, new + marker, 1))


# Scope interventions to the list physically belonging to the "Lista Intervenții"
# section. The previous find_all_next() walk escaped the card and consumed two
# footer <li> rows from every GAL page ("Lansată în data de..." and "Urmăriți-ne pe").
replace_between(
    'parsers.py',
    '    interventions = []\n',
    '\n    record = {',
    '''    interventions = []
    h_int = _find_heading(soup, "Lista Intervenții")
    if h_int:
        intervention_list = None

        # Preferred/current AFIR layout: heading followed by a card containing one <ul>.
        # Walk only siblings of the heading, and stop at the next heading. This creates a
        # hard DOM boundary and prevents footer/navigation lists from ever being considered.
        for sibling in h_int.next_siblings:
            if not isinstance(sibling, Tag):
                continue
            if sibling.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                break
            if sibling.name == "ul":
                intervention_list = sibling
                break
            candidate = sibling.find("ul")
            if candidate is not None:
                intervention_list = candidate
                break

        # Conservative fallback for minor markup changes: look inside the heading's direct
        # parent only. Never walk the whole remainder of the document.
        if intervention_list is None and isinstance(h_int.parent, Tag):
            parent_candidates = h_int.parent.find_all("ul", recursive=False)
            if parent_candidates:
                intervention_list = parent_candidates[0]

        if intervention_list is not None:
            for node in intervention_list.find_all("li", recursive=False):
                text = clean_text(node.get_text(" ", strip=True)).lstrip("• ")
                if not text:
                    continue
                m = re.match(
                    r"(?P<code>[A-Z]+\\d+)\\s*-\\s*(?P<name>.*?)(?:\\s*\\(Intervenție de tipul\\s*(?P<type>.*?)\\))?$",
                    text,
                    re.IGNORECASE,
                )
                if m:
                    interventions.append({
                        "code": m.group("code").upper(),
                        "name": clean_text(m.group("name")),
                        "type": clean_text(m.group("type")) or None,
                        "raw": text,
                    })
                else:
                    # Preserve unexpected rows only when they are genuinely inside the
                    # intervention card. QA treats an uncoded intervention as an ERROR so a
                    # future AFIR schema/code change cannot silently disappear.
                    interventions.append({"code": None, "name": text, "type": None, "raw": text})
''',
)

# Add explicit intervention-integrity checks. These are intentionally redundant with
# parser scoping: if AFIR changes its markup in the future, the national run fails loudly
# instead of exporting another contaminated master table.
insert_before(
    'quality.py',
    '    # National completeness contract:',
    '''    for row in store.query("SELECT gal_id,code,name,raw FROM interventions"):
        iid = f"{row['gal_id']}:{row.get('code') or row.get('name') or ''}"
        code = (row.get("code") or "").strip()
        name = (row.get("name") or "").strip()
        raw = (row.get("raw") or "").strip()
        if not code:
            issues.append(QualityIssue(
                "ERROR", "UNCODED_INTERVENTION", "intervention", iid,
                f"Intervention row has no recognized intervention code: {raw or name}"
            ))
        elif not re.fullmatch(r"[A-Za-z]+\\d+", code):
            issues.append(QualityIssue(
                "ERROR", "INVALID_INTERVENTION_CODE", "intervention", iid,
                f"Unexpected intervention code format: {code}"
            ))
        boilerplate = (name + " " + raw).casefold()
        if "urmăriți-ne pe" in boilerplate or "urmariti-ne pe" in boilerplate or "lansată în data de" in boilerplate or "lansata in data de" in boilerplate:
            issues.append(QualityIssue(
                "ERROR", "INTERVENTION_BOILERPLATE_CONTAMINATION", "intervention", iid,
                f"Footer/navigation text leaked into intervention table: {raw or name}"
            ))

''',
)

# Mark the patched runtime distinctly in diagnostic output/artifacts.
version = root / 'version.py'
if version.exists():
    version.write_text('__version__ = "2.2.0"\n')

print('cleanup fixes applied: bounded intervention DOM parsing + strict intervention QA')
