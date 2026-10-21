"""Measure an editor's culling style from one wedding they have already culled.
python3 cull_style.py <project.prproj> <inventory.json> <out_dir> [--stringouts Morning,Reception,Evening]

inventory.json comes from culling-wedding-footage's inventory.py (or has a "moment" per clip). Writes to out_dir:
selects.json (every select: stringout, path, in, out, track) and their_plan.json (the cull in plan form, for
compare_cull.py), and prints per moment: clips kept / clips, select lengths, head and tail trims, the colour on
the kept clips' project items, and whether clips run in filename or capture order.
"""
import json, os, statistics as st, subprocess, sys
from collections import Counter, defaultdict

if len(sys.argv) < 4:
    sys.exit(__doc__)
proj, inv_path, out = sys.argv[1:4]
names = (sys.argv[sys.argv.index('--stringouts') + 1] if '--stringouts' in sys.argv else 'Morning,Reception,Evening').split(',')
skills = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
dump = os.path.join(skills, 'building-wedding-multicam', 'scripts', 'prproj_dump.py')
labels = os.path.join(skills, 'culling-wedding-footage', 'scripts', 'master_labels.py')
os.makedirs(out, exist_ok=True)
inv = json.load(open(inv_path))
moment = lambda p: (inv.get(p) or {}).get('moment') or os.path.basename(os.path.dirname(p))

sel = []
for n in names:
    j = os.path.join(out, f'dump_{n}.json')
    subprocess.run([sys.executable, '-I', dump, proj, n, j], check=True, capture_output=True)
    for t in json.load(open(j))['tracks']:
        if t['type'] == 'video':
            for i in t['items']:
                if i.get('path'):
                    sel.append(dict(seq=n, track=t['index'] + 1, path=i['path'], start=i['start'],
                                    inn=i['in'], out=i['in'] + i['end'] - i['start']))
json.dump(sel, open(os.path.join(out, 'selects.json'), 'w'), indent=0)
subprocess.run([sys.executable, '-I', labels, proj, os.path.join(out, 'labels.json')], check=True, capture_output=True)
lab = json.load(open(os.path.join(out, 'labels.json')))

plan = {'sequences': []}
for n in names:
    secs = []
    for r in sorted((r for r in sel if r['seq'] == n), key=lambda r: (r['start'], r['track'])):
        m = moment(r['path'])
        if not secs or secs[-1]['name'] != m:
            secs.append({'name': m, 'colour': lab.get(r['path']) or 'Iris', 'clips': []})
        c = {'path': r['path'], 'in': r['inn'], 'out': r['out']}
        if r['track'] > 1:
            c['track'] = r['track']
        secs[-1]['clips'].append(c)
    plan['sequences'].append({'name': n, 'sections': secs})
json.dump(plan, open(os.path.join(out, 'their_plan.json'), 'w'), indent=1)

raw = Counter(moment(p) for p in inv)
pct = lambda xs, q: sorted(xs)[min(len(xs) - 1, int(q * len(xs)))]
inversions = lambda ks: sum(a > b for i, a in enumerate(ks) for b in ks[i + 1:])
order_name = order_time = 0
print(f"{'stringout':10s} {'moment':24s} kept/clips   median  p10  p90  head tail  colour")
for sq in plan['sequences']:
    for s in sq['sections']:
        ps = list(dict.fromkeys(c['path'] for c in s['clips']))
        lens = [c['out'] - c['in'] for c in s['clips']]
        heads = [c['in'] for c in s['clips']]
        tails = [inv[c['path']]['dur'] - c['out'] for c in s['clips'] if c['path'] in inv]
        cols = Counter(lab.get(p) for p in ps).most_common(1)[0][0]
        order_name += inversions([os.path.basename(p) for p in ps])
        order_time += inversions([(inv.get(p) or {}).get('ct') or '' for p in ps])
        print(f"{sq['name']:10s} {s['name']:24s} {len(ps):3d}/{raw.get(s['name'], len(ps)):<4d}  "
              f"{st.median(lens):6.1f} {pct(lens, .1):4.1f} {pct(lens, .9):4.1f}  {st.median(heads):4.1f} "
              f"{st.median(tails) if tails else 0:4.1f}  {cols}")
alll = [r['out'] - r['inn'] for r in sel]
print(f"\n{len(sel)} selects from {len({r['path'] for r in sel})} clips; median {st.median(alll):.1f} s, "
      f"p10 {pct(alll, .1):.1f}, p90 {pct(alll, .9):.1f}")
print(f"clip order: {order_name} pairs out of filename order, {order_time} out of capture order "
      f"({'filename' if order_name <= order_time else 'capture'} order fits better)")
