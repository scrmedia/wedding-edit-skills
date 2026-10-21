"""Contact sheets of a cut plan: the middle frame of every planned multicam shot, from the angle's source file.

  python3 plan_sheet.py <plan.json> <nest.json> <out_prefix>

plan.json "video": [{"start": nest_s, "end": nest_s, "angle": n}, ...]. Writes <out_prefix>_NN.jpg (36 shots each).
"""
import json, os, subprocess, sys, tempfile
if len(sys.argv) != 4:
    sys.exit(__doc__)
plan, nest = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
angles = {t['index']: t['items'] for t in nest['tracks'] if t['type'] == 'video'}
tmp, frames = tempfile.mkdtemp(prefix='plan-'), []
for k, c in enumerate(plan['video']):
    mid = (c['start'] + c['end']) / 2
    src = next(((it['path'], it['in'] + mid - it['start']) for it in angles[c['angle']] if it['start'] <= mid < it['end']), None)
    if not src:
        print('shot', k, 'angle', c['angle'], 'has no picture at', mid); continue
    out = f'{tmp}/{k:04d}.jpg'
    lab = f"{k} {c['start']:.0f}s ang{c['angle']} {c['end'] - c['start']:.0f}s"
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f'{src[1]:.2f}', '-i', src[0], '-frames:v', '1', '-vf',
                    f"scale=320:-2,drawtext=text='{lab}':fontcolor=yellow:fontsize=14:x=4:y=4:box=1:boxcolor=black@0.6,format=yuvj420p", out])
    if os.path.exists(out):
        frames.append(out)
for n in range(0, len(frames), 36):
    ch = frames[n:n + 36]
    lay = '|'.join(f'{(i % 6) * 320}_{(i // 6) * 180}' for i in range(len(ch)))
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', *sum((['-i', f] for f in ch), []), '-filter_complex',
                    f'xstack=inputs={len(ch)}:layout={lay}:fill=black', f'{sys.argv[3]}_{n // 36:02d}.jpg'], check=True)
    print(f'{sys.argv[3]}_{n // 36:02d}.jpg', len(ch))
