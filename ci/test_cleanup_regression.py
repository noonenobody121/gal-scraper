from afir_gal.parsers import parse_call_detail, parse_gal_detail

GAL_HTML = r'''
<html><body>
<div title="TEST GAL">
  <div><span>Cod : 999</span><span>Cui : 123</span><span>Județ : XX</span></div>
</div>
<div class="row">
  <div class="col-md-6">
    <h2>Lista localități cuprinse în strategia GAL</h2>
    <div><ul><li>TEST LOCALITY</li></ul></div>
  </div>
  <div class="col-md-6">
    <h2>Lista Intervenții</h2>
    <div class="card">
      <ul>
        <li><span>•</span> L805 - START-UP TEST (Intervenție de tipul Start-up)</li>
        <li><span>•</span> FSE1 - INCLUZIUNE TEST</li>
      </ul>
    </div>
  </div>
</div>
<footer>
  <ul>
    <li>Lansată în data de 20.06.2025</li>
    <li>Urmăriți-ne pe</li>
  </ul>
</footer>
</body></html>
'''

gal = parse_gal_detail(
    GAL_HTML,
    'https://gal.afir.ro/Gal?g=11111111-1111-4111-8111-111111111111',
)
rows = gal['interventions']
assert len(rows) == 2, rows
assert [x['code'] for x in rows] == ['L805', 'FSE1'], rows
assert all('Lansată în data' not in x['raw'] for x in rows), rows
assert all('Urmăriți-ne pe' not in x['raw'] for x in rows), rows

CALL_HTML = r'''
<html><body>
<div class="d-flex gap-2"><span>Titlu anunț :</span><span>TEST CALL:</span></div>
<div class="d-flex gap-2"><span>Intervenție SDL :</span><span>START-UP TEST</span></div>
<div class="d-flex gap-2"><span>Data lansare apel de selecție :</span><span>30.04.2026 09:00</span></div>
<div class="d-flex gap-2"><span>Data limită de depunere proiecte :</span><span>30.05.2026 23:59</span></div>
<table>
  <thead><tr><th>Nr. crt.</th><th>Descriere status</th><th>Data</th></tr></thead>
  <tbody><tr><td>1</td><td>Apelul de selecție creat</td><td>30.04.2026 12:38</td></tr></tbody>
</table>
</body></html>
'''
call = parse_call_detail(
    CALL_HTML,
    'https://gal.afir.ro/GalApel/VizualizareApelSelectie?idApelSelectie=22222222-2222-4222-8222-222222222222&nrPagina=1',
    gal_id='11111111-1111-4111-8111-111111111111',
)
keys = {x['key'] for x in call['raw_fields']}
assert keys == {
    'titlu_anunt', 'interventie_sdl', 'data_lansare_apel_de_selectie', 'data_limita_de_depunere_proiecte'
}, call['raw_fields']
assert len(call['statuses']) == 1, call['statuses']
assert not any(k.startswith('nr_crt_descriere_status_data') for k in keys), keys
assert call['title'] == 'TEST CALL:', call['title']
print('cleanup regressions PASS: intervention scope + structured raw fields + status-table isolation')
