"""Compare a cull (Claude's plan) with the editor's stringouts, per moment folder.
python3 compare_cull.py <plan.json> <selects.json> <inventory.json>

plan.json: {"sequences": [{"name": "Morning", "sections": [{"name": "Bride Prep", "colour": "Rose",
            "clips": [{"path": ..., "in": s, "out": s}, ...]}, ...]}, ...]}
Per folder: raw files, kept by the editor / Claude / both, recall (share of their kept files we kept), precision,
chance recall (our count / raw files), kept seconds, and for shared files the overlap of the two ranges
(intersection / union) and whether our range covers the middle of his.
"""
import json, os, statistics as st, sys
from collections import defaultdict
if len(sys.argv) < 4:
    sys.exit(__doc__)

plan, sel, inv = (json.load(open(p)) for p in sys.argv[1:4])
# moment = inventory's 'moment' field when the raw files no longer sit in moment folders, else the parent folder
folder = lambda p: inv.get(p, {}).get('moment') or os.path.basename(os.path.dirname(p))
raw = defaultdict(set)
for p in inv:
    raw[folder(p)].add(p)
his, ours = defaultdict(list), defaultdict(list)
for r in sel:
    his[r['path']].append((r['inn'], r['inn'] + r['dur']))
for sq in plan['sequences']:
    for sec in sq['sections']:
        for c in sec['clips']:
            ours[c['path']].append((c['in'], c['out']))


def secs(d, files):
    return sum(b - a for f in files for a, b in d[f])


def iou(r1, r2):
    inter = sum(max(0, min(b1, b2) - max(a1, a2)) for a1, b1 in r1 for a2, b2 in r2)
    union = sum(b - a for a, b in r1) + sum(b - a for a, b in r2) - inter
    return inter / union if union else 0


print(f"{'folder':20s} raw  his ours both  recall prec chance   his_s ours_s  IoU  mid")
tot = defaultdict(float)
for fo in sorted(raw, key=lambda f: min(raw[f])):
    files = raw[fo]
    h = {f for f in files if f in his}
    o = {f for f in files if f in ours}
    if not h and not o:
        continue
    b = h & o
    ious = [iou(his[f], ours[f]) for f in b]
    mids = [any(a <= (ha + hb) / 2 <= z for a, z in ours[f]) for f in b for ha, hb in his[f]]
    rec, prec, ch = len(b) / len(h) if h else 0, len(b) / len(o) if o else 0, len(o) / len(files)
    print(f"{fo:20s} {len(files):3d}  {len(h):3d}  {len(o):3d}  {len(b):3d}   {rec:4.0%}  {prec:4.0%}  {ch:4.0%}  "
          f"{secs(his, h):6.0f} {secs(ours, o):6.0f}  {st.mean(ious) if ious else 0:4.2f} {sum(mids)}/{len(mids)}")
    for k, v in (('raw', len(files)), ('his', len(h)), ('ours', len(o)), ('both', len(b))):
        tot[k] += v
print(f"{'ALL':20s} {tot['raw']:3.0f}  {tot['his']:3.0f}  {tot['ours']:3.0f}  {tot['both']:3.0f}   "
      f"{tot['both'] / tot['his']:4.0%}  {tot['both'] / max(tot['ours'], 1):4.0%}  {tot['ours'] / tot['raw']:4.0%}")
