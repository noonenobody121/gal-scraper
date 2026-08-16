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

# Make structured AFIR call-detail label/value groups authoritative. The old generic
# fallback scanned the status-history table too; timestamps such as 12:38 were therefore
# misread as fake label:value schema fields. Status history already has a dedicated parser.
replace_between(
    'parsers.py',
    'def _extract_label_values(soup: BeautifulSoup) -> tuple[dict[str, str], list[dict[str, str]]]:',
    '\n\ndef parse_call_detail',
    '''def _extract_label_values(soup: BeautifulSoup) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Extract AFIR call label:value pairs without leaking table/status noise.

    Current AFIR call attributes are rendered as a container with direct span children:
    the first span is the label (ending in ':') and the remaining span(s) form the value.
    We prefer that semantic structure and only use conservative fallbacks when it is absent.
    """
    pairs: dict[str, str] = {}
    raw_fields: list[dict[str, str]] = []
    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []

    # Primary/current AFIR structure. This also automatically captures future fields that
    # use the same layout, while excluding the status-history table and footer content.
    for group in soup.find_all(["div", "p", "li", "td"]):
        spans = group.find_all("span", recursive=False)
        if len(spans) < 2:
            continue
        label = clean_text(spans[0].get_text(" ", strip=True)).rstrip()
        if not label.endswith(":"):
            continue
        value = clean_text(" ".join(x.get_text(" ", strip=True) for x in spans[1:]))
        if value:
            candidates.append((label.rstrip(":"), value))

    # Secondary layout: strong/b/label/dt followed by value siblings. Only use this when
    # the structured span layout is absent, so broad DOM text cannot contaminate a normal page.
    if not candidates:
        for label_tag in soup.find_all(["strong", "b", "label", "dt"]):
            label_text = clean_text(label_tag.get_text(" ", strip=True))
            if not label_text.endswith(":"):
                continue
            value_parts = []
            for sib in label_tag.next_siblings:
                if getattr(sib, "name", None) in {"strong", "b", "label", "dt"}:
                    break
                text = clean_text(sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib))
                if text:
                    value_parts.append(text)
            if value_parts:
                candidates.append((label_text.rstrip(":"), clean_text(" ".join(value_parts))))

    # Last-resort support for simple/server-rendered fixtures. Do not scan tables: colons in
    # times are data, not field separators. This fallback is intentionally conservative.
    if not candidates:
        for tag in soup.find_all(["p", "div", "span", "li"]):
            if tag.find_parent("table") is not None:
                continue
            if tag.find(["p", "div", "span", "li"], recursive=False):
                continue
            txt = clean_text(tag.get_text(" ", strip=True))
            if ":" not in txt:
                continue
            label, value = txt.split(":", 1)
            label, value = clean_text(label), clean_text(value)
            if label and value:
                candidates.append((label, value))

    for label, value in candidates:
        if not label or not value or len(label) > 120:
            continue
        key = ascii_key(label)
        if key in seen:
            continue
        # Defensive filters for status/table artefacts if AFIR changes markup again.
        if re.search(r"\\b\\d{1,2}\\.\\d{1,2}\\.\\d{4}\\b", label):
            continue
        if key.startswith("nr_crt_descriere_status_data") or key in {"nr_crt", "descriere_status", "data"}:
            continue
        if re.match(r"^\\d", label) or (any(ch.isdigit() for ch in label) and "/" in label):
            continue
        if len(label.split()) > 12:
            continue
        if any(noise in key for noise in (
            "publicat_pe_acest_apel", "termen_limita_perioada_contestatii",
            "raport_de_selectie_intermediar", "raport_de_selectie_final", "raport_de_selectie_suplimentar",
        )):
            continue
        if key in {"cod_proiect", "tip_document", "cerere_de_plata"}:
            continue
        seen.add(key)
        pairs[key] = value
        raw_fields.append({"label": label, "key": key, "value": value})

    return pairs, raw_fields
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
    version.write_text('__version__ = "2.2.1"\n')

print('cleanup fixes applied: bounded interventions + structured raw fields + strict QA')
