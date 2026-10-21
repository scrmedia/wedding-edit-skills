"""Filmstrip sheets of every raw file in a moment: one row per file, frames evenly across it, time-stamped.
python3 cull_strips.py <folder | inventory.json:Moment> <selects.json|-> <out_prefix> [--rows 8] [--frames 5]

The source is a moment folder, or a moment named in an inventory ({path: {"moment", "ct", ...}}) when the raw
files sit in camera folders. Rows run in capture order. With a selects file, frames inside a kept range are boxed
green and the first caption says KEPT a-b or DROPPED (for studying a finished cull); with "-" nothing is marked.
Prints one sheet path per line."""
import json, os, subprocess, sys, tempfile, glob
if len(sys.argv) < 4:
    sys.exit(__doc__)

src, sel, out = sys.argv[1], sys.argv[2], sys.argv[3]
arg = lambda name, d: int(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else d
rows_per, nfr = arg('--rows', 8), arg('--frames', 5)
kept = {}
if sel != '-':
    for r in json.load(open(sel)):
        kept.setdefault(r['path'], []).append((r['inn'], r['inn'] + r['dur']))
if os.path.isdir(src):
    files = sorted(f for f in glob.glob(os.path.join(src, '*')) if f.upper().endswith(('.MP4', '.MOV')))
else:
    inv_path, moment = src.split('.json:', 1)  # moment names can contain ':'
    inv_path += '.json'
    inv = json.load(open(inv_path))
    files = sorted((f for f, x in inv.items() if x.get('moment') == moment), key=lambda f: (inv[f].get('ct') or '', f))
tmp = tempfile.mkdtemp(prefix='strips-')
W, H = 256, 144


def row(k, f):
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f],
                               capture_output=True, text=True).stdout)
    ks = kept.get(f, [])
    tag = '' if sel == '-' else ('KEPT ' + ' '.join(f'{a:.1f}-{b:.1f}' for a, b in ks)) if ks else 'DROPPED'
    cells = []
    for j in range(nfr):
        t = dur * (0.04 + 0.92 * j / max(nfr - 1, 1))
        o = f'{tmp}/{k:03d}_{j}.jpg'
        lab = (f"{os.path.basename(f)} {dur:.1f}s {tag} | {t:.1f}s" if j == 0 else f"{t:.1f}s").replace(':', ' ')
        box = 'drawbox=x=0:y=0:w=iw:h=ih:color=lime:t=8,' if any(a <= t <= b for a, b in ks) else ''
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-hwaccel', 'videotoolbox', '-ss', f'{t:.2f}', '-i', f,
                        '-frames:v', '1', '-vf', f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,{box}drawtext=text='{lab}':fontcolor=yellow:fontsize=11:"
                        "x=3:y=3:box=1:boxcolor=black@0.7,format=yuvj420p", o])
        cells.append(o if os.path.exists(o) else None)
    return cells


for n in range(0, len(files), rows_per):  # each sheet is written as soon as its rows are done
    chunk = [c for k in range(n, min(n + rows_per, len(files))) for c in row(k, files[k])]
    ok = [(i, c) for i, c in enumerate(chunk) if c]
    lay = '|'.join(f'{(i % nfr) * W}_{(i // nfr) * H}' for i, _ in ok)
    stack = ['-filter_complex', f'xstack=inputs={len(ok)}:layout={lay}:fill=black'] if len(ok) > 1 else []
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', *sum((['-i', c] for _, c in ok), []), *stack,
                    f'{out}_{n // rows_per:02d}.jpg'], check=True)
    print(f'{out}_{n // rows_per:02d}.jpg', flush=True)
