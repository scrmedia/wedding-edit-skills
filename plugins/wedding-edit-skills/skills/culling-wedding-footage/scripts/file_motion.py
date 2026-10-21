"""Camera shift every 0.1 s for raw files (skips Ceremony/Speeches multicam folders).
python3 file_motion.py <inventory.json> <out.json> [--only selects.json] [--jobs 3]
  -> {path: [[t, px_per_frame], ...]}  (resumable; --only limits it to the files a cull kept)
Median local motion vector from ffmpeg vidstabdetect at 10 fps on a 320 px copy: the camera's own move,
0 on a locked-off shot. Hardware decode where VideoToolbox can (A7S HEVC, drone); Panasonic 10-bit
H.264 falls back to software (slow)."""
import json, os, re, statistics as st, subprocess, sys, tempfile, threading
from concurrent.futures import ThreadPoolExecutor
if len(sys.argv) < 3:
    sys.exit(__doc__)
inv, out = json.load(open(sys.argv[1])), sys.argv[2]
only = {r['path'] for r in json.load(open(sys.argv[sys.argv.index('--only') + 1]))} if '--only' in sys.argv else None
jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 3
res = json.load(open(out)) if os.path.exists(out) else {}
tmp, lock = tempfile.mkdtemp(prefix='fmotion-'), threading.Lock()


def scan(k, f):
    trf = f'{tmp}/{k}.trf'
    subprocess.run(['ffmpeg', '-v', 'quiet', '-hwaccel', 'videotoolbox', '-i', f, '-vf', f'fps=10,scale=320:-2,'
                    f'vidstabdetect=result={trf}:shakiness=10:accuracy=15:stepsize=6:fileformat=ascii', '-f', 'null', '-'])
    series = []
    if os.path.exists(trf):
        for n, body in re.findall(r'Frame (\d+) \(List \d+ \[(.*?)\]\)', open(trf, errors='replace').read()):
            lms = [(int(x), int(y)) for x, y in re.findall(r'LM (-?\d+) (-?\d+) ', body)]
            sh = ((st.median(x for x, _ in lms) ** 2 + st.median(y for _, y in lms) ** 2) ** 0.5) if lms else 0.0
            series.append([round((int(n) - 1) / 10, 1), round(sh, 1)])
        os.remove(trf)
    with lock:
        res[f] = series
        json.dump(res, open(out, 'w'))
        print(len(res), os.path.basename(f), flush=True)


todo = [f for f in sorted(inv) if f not in res and '/Ceremony/' not in f and '/Speeches/' not in f
        and (only is None or f in only)]
with ThreadPoolExecutor(jobs) as ex:
    list(ex.map(scan, range(len(todo)), todo))
print('done', len(res), flush=True)
