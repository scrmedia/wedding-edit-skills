"""List every raw clip of a wedding by part of the day and moment.
python3 inventory.py <wedding folder> <out.json> [--from-project <project.prproj>]
  -> {path: {"part", "moment", "dur", "ct", "fps", "w"}}
Moments are the folders under Morning/, Reception/, Evening/; a top-level Aerial (or Drone) folder is its own
moment with part "Aerial". Ceremony and Speeches are skipped (they are multicams). ct = capture time from the
file's creation_time tag, for ordering.

--from-project: for a wedding whose raw has since gone back into camera folders (an archive). The moment of each
clip comes from the paths the editor's project recorded (.../Morning/Bride Prep/A7S-9031.MP4), matched by file
name to the clips found anywhere under the wedding folder. File names must be unique across cameras.
"""
import glob, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
if len(sys.argv) < 3:
    sys.exit(__doc__)

root, out = sys.argv[1], sys.argv[2]
files = []
if '--from-project' in sys.argv:
    import gzip, re
    proj = sys.argv[sys.argv.index('--from-project') + 1]
    raw = open(proj, 'rb').read()
    text = (gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw).decode('utf8', 'replace')
    where = {}
    for path in re.findall(r'<(?:ActualMediaFilePath|FilePath)>([^<]*/[^<]+)<', text):
        parts = path.replace('\\', '/').split('/')
        if len(parts) >= 3 and parts[-3] in ('Morning', 'Reception', 'Evening') and parts[-2] not in ('Ceremony', 'Speeches'):
            where[parts[-1]] = (parts[-3], parts[-2])
        elif len(parts) >= 2 and parts[-2] in ('Aerial', 'Drone'):
            where[parts[-1]] = ('Aerial', parts[-2])
    for f in glob.glob(os.path.join(root, '**', '*'), recursive=True):
        if os.path.basename(f) in where:
            files.append((f, *where[os.path.basename(f)]))
    print(f'{len(files)} of {len(where)} clips the project placed in moments were found under {root}')
for part in ('Morning', 'Reception', 'Evening') if not files else ():
    for f in glob.glob(os.path.join(root, part, '*', '*')):
        moment = os.path.basename(os.path.dirname(f))
        if moment not in ('Ceremony', 'Speeches'):
            files.append((f, part, moment))
for aerial in ('Aerial', 'Drone') if not any(p == 'Aerial' for _, p, _ in files) else ():
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
