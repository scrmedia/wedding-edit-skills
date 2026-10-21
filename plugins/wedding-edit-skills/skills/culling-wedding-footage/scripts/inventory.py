"""List every raw clip of a wedding by part of the day and moment.
python3 inventory.py <wedding folder> <out.json>
  -> {path: {"part", "moment", "dur", "ct", "fps", "w"}}
Moments are the folders under Morning/, Reception/, Evening/; a top-level Aerial (or Drone) folder is its own
moment with part "Aerial". Ceremony and Speeches are skipped (they are multicams). ct = capture time from the
file's creation_time tag, for ordering.
"""
import glob, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
if len(sys.argv) < 3:
    sys.exit(__doc__)

root, out = sys.argv[1], sys.argv[2]
files = []
for part in ('Morning', 'Reception', 'Evening'):
    for f in glob.glob(os.path.join(root, part, '*', '*')):
        moment = os.path.basename(os.path.dirname(f))
        if moment not in ('Ceremony', 'Speeches'):
            files.append((f, part, moment))
for aerial in ('Aerial', 'Drone'):
    files += [(f, 'Aerial', aerial) for f in glob.glob(os.path.join(root, aerial, '*'))]
files = [x for x in files if x[0].upper().endswith(('.MP4', '.MOV'))]


def probe(f):
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,'
                                   'r_frame_rate,width:stream_tags=creation_time', '-of', 'json', f],
                                  capture_output=True, text=True).stdout)
    v = next(s for s in j['streams'] if s['codec_type'] == 'video')
    return dict(dur=float(j['format']['duration']), ct=v.get('tags', {}).get('creation_time'), fps=v['r_frame_rate'],
                w=v['width'])


with ThreadPoolExecutor(8) as ex:
    info = list(ex.map(probe, [f for f, _, _ in files]))
inv = {f: dict(part=p, moment=m, **i) for (f, p, m), i in zip(files, info)}
json.dump(inv, open(out, 'w'), indent=0)
n = {}
for x in inv.values():
    n[(x['part'], x['moment'])] = n.get((x['part'], x['moment']), 0) + 1
for (p, m), c in sorted(n.items()):
    print(f'{p:10s} {m:24s} {c:4d}')
