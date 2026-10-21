#!/usr/bin/env python3
"""Find when each multicam angle is repositioning (camera movement), so a cut never shows it.

  python3 motion_scan.py <nest.json> <out.json> [--start 0] [--end N] [--threshold 1.0]
  python3 motion_scan.py check <plan.json> <motion.json> [--threshold 3] [--allow 0-148]
      shots that show an angle moving faster than the threshold, outside the --allow ranges (nest s)

For every video angle in nest.json (prproj_dump.py of the multicam source) it runs ffmpeg vidstabdetect
at 10 fps on a 320 px copy and takes, per frame, the median of the local motion vectors: the camera's own
shift in pixels. People moving inside a static frame barely move the median (it reads exactly 0 on a
locked-off shot), so this flags camera moves, not busy scenes. Writes per-second shift and the moving
windows in nest time: {"angles": {"0": {"per_second": [...], "moving": [[start, end], ...]}}}.
Threshold: mean shift above 1.0 px per frame over a second counts as moving; windows are padded 0.5 s.
Calibrated on a reference wedding: a visible reposition read 3-18 px/frame, a locked shot 0.0. The editor's own ceremony cut
shows movement above 3 px/frame only in the processional (deliberate follow moves on the walk) plus two
brief moments; check with --threshold 3 --allow <processional range>.
Software decode (the Panasonic 10-bit H.264 won't hardware-decode): about 25 s per minute of 4K.
"""
import argparse, json, os, re, statistics as st, subprocess, sys, tempfile

if len(sys.argv) == 1:
    sys.exit(__doc__)
if sys.argv[1] == 'check':
    plan, mo = json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
    thr = float(sys.argv[sys.argv.index('--threshold') + 1]) if '--threshold' in sys.argv else 3.0
    allow = [tuple(map(float, r.split('-'))) for r in sys.argv[sys.argv.index('--allow') + 1:] if '-' in r] \
        if '--allow' in sys.argv else []
    bad = 0
    for k, c in enumerate(plan['video']):
        ang = mo['angles'].get(str(c['angle']), {})
        if ang.get('per_tenth'):  # frame-level: any 0.1 s on screen above the threshold
            hits = [(t, v) for t, v in ang['per_tenth'] if c['start'] <= t < c['end'] and v > thr
                    and not any(a <= t < b for a, b in allow)]
        else:  # older scans: per second, with half a second of slack at the shot edges
            hits = [(x, v) for x, v in ang.get('per_second', []) if c['start'] - 0.5 <= x < c['end'] - 0.5 and v > thr
                    and not any(a <= x < b for a, b in allow)]
        if hits:
            bad += 1
            print(f"shot {k} {c['start']:.1f}-{c['end']:.1f} angle {c['angle']}: moving at {hits[0][0]}-{hits[-1][0]} s, "
                  f"peak {max(v for _, v in hits):.1f} px/frame")
    print(f'{bad} shot(s) show a camera move above {thr} px/frame')
    sys.exit(1 if bad else 0)
ap = argparse.ArgumentParser()
ap.add_argument('nest'); ap.add_argument('out')
ap.add_argument('--start', type=float, default=0); ap.add_argument('--end', type=float)
ap.add_argument('--threshold', type=float, default=1.0)
a = ap.parse_args()
nest = json.load(open(a.nest))
out = {'threshold_px_per_frame': a.threshold, 'angles': {}}
tmp = tempfile.mkdtemp(prefix='motion-')
for t in sorted((t for t in nest['tracks'] if t['type'] == 'video'), key=lambda t: t['index']):
    per_sec, per_tenth = {}, {}
    for it in t['items']:
        lo, hi = max(it['start'], a.start), min(it['end'], a.end if a.end else it['end'])
        if hi <= lo:
            continue
        trf = f"{tmp}/a{t['index']}_{lo:.0f}.trf"
        subprocess.run(['ffmpeg', '-v', 'quiet', '-ss', f"{it['in'] + lo - it['start']:.3f}", '-t', f'{hi - lo:.3f}',
                        '-i', it['path'], '-vf', f'fps=10,scale=320:-2,vidstabdetect=result={trf}:shakiness=10:'
                        'accuracy=15:stepsize=6:fileformat=ascii', '-f', 'null', '-'], check=True)
        frames = re.findall(r'Frame (\d+) \(List \d+ \[(.*?)\]\)', open(trf, errors='replace').read())
        for n, body in frames:
            lms = [(int(x), int(y)) for x, y in re.findall(r'LM (-?\d+) (-?\d+) ', body)]
            shift = ((st.median(x for x, _ in lms) ** 2 + st.median(y for _, y in lms) ** 2) ** 0.5) if lms else 0.0
            t10 = round(lo + (int(n) - 1) / 10, 1)
            per_tenth[t10] = round(shift, 1)
            per_sec.setdefault(int(t10), []).append(shift)
    secs = sorted(per_sec)
    series = [[s, round(sum(per_sec[s]) / len(per_sec[s]), 2)] for s in secs]
    moving = []
    for s, v in series:
        if v > a.threshold:
            if moving and s - 0.5 <= moving[-1][1]:
                moving[-1][1] = s + 1.5
            else:
                moving.append([s - 0.5, s + 1.5])
    out['angles'][str(t['index'])] = {'path': t['items'][0]['path'], 'per_second': series, 'moving': moving,
                                      'per_tenth': sorted(per_tenth.items())}
    print(f"angle {t['index']} {os.path.basename(t['items'][0]['path'])}: {len(moving)} moving windows, "
          f"{sum(e - s for s, e in moving):.0f} s", flush=True)
json.dump(out, open(a.out, 'w'))
