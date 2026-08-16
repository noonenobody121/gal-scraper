from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'ci-src') / 'afir_gal'
p = root / 'storage.py'
s = p.read_text()
old = '''        self.db.execute("DELETE FROM localities WHERE gal_id=?", (r["gal_id"],))
        self.db.executemany("INSERT OR IGNORE INTO localities(gal_id,locality) VALUES(?,?)", [(r["gal_id"], x) for x in r.get("localities", [])])
        self.db.execute("DELETE FROM interventions WHERE gal_id=?", (r["gal_id"],))
'''
new = '''        self.db.execute("DELETE FROM localities WHERE gal_id=?", (r["gal_id"],))
        self.db.executemany("INSERT OR IGNORE INTO localities(gal_id,locality) VALUES(?,?)", [(r["gal_id"], x) for x in r.get("localities", [])])
        # Keep the derived locality-resolution table synchronized with the authoritative
        # current GAL territory. Previously, a locality removed by AFIR could leave an
        # orphaned SIRUTA resolution behind across incremental reruns.
        self.db.execute(
            "DELETE FROM locality_resolution WHERE gal_id=? AND locality NOT IN "
            "(SELECT locality FROM localities WHERE gal_id=?)",
            (r["gal_id"], r["gal_id"]),
        )
        self.db.execute("DELETE FROM interventions WHERE gal_id=?", (r["gal_id"],))
'''
if old not in s:
    raise SystemExit('missing storage locality anchor')
p.write_text(s.replace(old, new, 1))
print('storage fix applied: stale locality resolutions are pruned on GAL updates')
