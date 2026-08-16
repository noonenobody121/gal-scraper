from afir_gal.parsers import parse_gal_detail

HTML = r'''
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

record = parse_gal_detail(
    HTML,
    'https://gal.afir.ro/Gal?g=11111111-1111-4111-8111-111111111111',
)
rows = record['interventions']
assert len(rows) == 2, rows
assert [x['code'] for x in rows] == ['L805', 'FSE1'], rows
assert all('Lansată în data' not in x['raw'] for x in rows), rows
assert all('Urmăriți-ne pe' not in x['raw'] for x in rows), rows
print('cleanup regression PASS:', rows)
