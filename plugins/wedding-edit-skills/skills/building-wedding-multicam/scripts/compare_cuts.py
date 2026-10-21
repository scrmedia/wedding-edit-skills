#!/usr/bin/env python3
"""Compare a cut plan (Claude's) with a finished multicam sequence (the editor's), in nest time.

  python3 compare_cuts.py <plan.json> <finished_seq.json> <nest.json> [--sections sections.json]

finished_seq.json and nest.json come from prproj_dump.py. sections.json (optional): [["name", start, end], ...]
in nest seconds, for per-section agreement. Prints: span, shots, holds, angle shares, how much of the time
both cuts show the same angle, how many of the editor's cuts have one of ours within 1 s, and mic overlap.
"""
import json, os, statistics as st, sys
from collections import defaultdict

if len(sys.argv) < 4:
    sys.exit(__doc__)
plan, seq, nest = (json.load(open(p)) for p in sys.argv[1:4])
sections = json.load(open(sys.argv[sys.argv.index('--sections') + 1])) if '--sections' in sys.argv else []

# The editor's cut -> plan form (nest time)
vt = max((t for t in seq['tracks'] if t['type'] == 'video'), key=lambda t: sum('multicamAngle' in i for i in t['items']))
ref = []
for i in vt['items']:
    if 'multicamAngle' in i:
        s = i['in']
        ref.append(dict(start=s, end=s + i['end'] - i['start'], angle=i['multicamAngle']))
mic_in = {os.path.splitext(os.path.basename(t['items'][0]['path']))[0].replace(' ', '_'): t['items'][0]['in']
          for t in nest['tracks'] if t['type'] == 'audio' and t['items']}
for name, x in plan.get('extra_sources', {}).items():
    mic_in[name] = x['offset']
ref_audio = defaultdict(list)
for t in seq['tracks']:
    if t['type'] != 'audio':
        continue
    for i in t['items']:
        mic = os.path.splitext(os.path.basename(i.get('path') or ''))[0].replace(' ', '_')
        if mic in mic_in:
            s = i['in'] - mic_in[mic]
            ref_audio[mic].append((s, s + i['end'] - i['start']))
ours_audio = defaultdict(list)
for x in plan.get('audio', []):
    ours_audio[x['mic']].append((x['start'], x['end']))


def angle_at(cuts, t):
    return next((c['angle'] for c in cuts if c['start'] <= t < c['end']), None)


def summary(name, cuts):
    d = [c['end'] - c['start'] for c in cuts]
    share = defaultdict(float)
    for c in cuts:
        share[c['angle']] += c['end'] - c['start']
    tot = sum(d)
    print(f"{name:8s} {cuts[0]['start']:7.1f}-{cuts[-1]['end']:7.1f}s  {len(cuts):3d} shots  median {st.median(d):4.1f}s  "
          f"mean {st.mean(d):4.1f}s  " + '  '.join(f'ang{k} {100 * v / tot:3.0f}%' for k, v in sorted(share.items())))


summary('Editor', ref)
summary('Claude', plan['video'])
lo, hi = max(ref[0]['start'], plan['video'][0]['start']), min(ref[-1]['end'], plan['video'][-1]['end'])
steps = [lo + k * 0.2 for k in range(int((hi - lo) / 0.2))]
same = sum(angle_at(ref, t) == angle_at(plan['video'], t) for t in steps)


def shares(cuts, a, b):
    out = defaultdict(float)
    for c in cuts:
        out[c['angle']] += max(0, min(c['end'], b) - max(c['start'], a))
    tot = sum(out.values()) or 1
    return {k: v / tot for k, v in out.items()}


sr, so = shares(ref, lo, hi), shares(plan['video'], lo, hi)
chance = sum(sr.get(k, 0) * so.get(k, 0) for k in set(sr) | set(so))
print(f'same angle on screen: {100 * same / len(steps):.0f}% of the shared {hi - lo:.0f} s '
      f'(chance with these shares: {100 * chance:.0f}%)')
ours_cuts = [c['start'] for c in plan['video'][1:]]
near = sum(any(abs(c['start'] - o) <= 1.0 for o in ours_cuts) for c in ref[1:])
print(f"Editor's cuts with one of ours within 1 s: {near}/{len(ref) - 1}")
for name, a, b in sections:
    pts = [t for t in steps if a <= t < b]
    if pts:
        agree = sum(angle_at(ref, t) == angle_at(plan['video'], t) for t in pts)
        fmt = lambda d: ' '.join(f'{k}:{100 * v:2.0f}' for k, v in sorted(d.items()))
        print(f'  {name:26s} {a:5.0f}-{b:5.0f}  same {100 * agree / len(pts):3.0f}%   '
              f'Editor [{fmt(shares(ref, a, b))}]  Claude [{fmt(shares(plan["video"], a, b))}]')


def overlap(r1, r2):
    return sum(max(0, min(b1, b2) - max(a1, a2)) for a1, b1 in r1 for a2, b2 in r2)


print('mics (seconds open: editor / Claude / both):')
for mic in sorted(set(ref_audio) | set(ours_audio)):
    r, o = ref_audio.get(mic, []), ours_audio.get(mic, [])
    print(f"  {mic:20s} {sum(b - a for a, b in r):6.0f} / {sum(b - a for a, b in o):6.0f} / {overlap(r, o):6.0f}")
