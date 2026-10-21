#!/usr/bin/env python3
"""Camera capture times and clock offsets.

  python3 capture_times.py scan <media_root> <out.json>
      ffprobe every .MP4/.MOV under media_root (skips Premiere cache folders).
  python3 capture_times.py offset <times.json> <refClip> <refStart> <refIn> <otherClip> <otherStart> <otherIn>
      Clock offset of the other clip's camera vs the reference camera, from one synced pair
      (timeline start and source in-point of each, in seconds, as they sit in a synced stack).
      Positive = the other camera's clock runs ahead. Confirm with a second synced pair.
"""
import json, os, subprocess, sys, datetime as dt


def scan(root, out):
    rows = []
    for r, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith('Adobe Premiere') and not d.startswith('.')]
        for f in fs:
            if f.startswith('.') or not f.upper().endswith(('.MP4', '.MOV')):
                continue
            p = os.path.join(r, f)
            j = json.loads(subprocess.run(
                ['ffprobe', '-v', 'error', '-print_format', 'json', '-show_entries',
                 'format=duration:format_tags=creation_time:stream_tags=timecode', p],
                capture_output=True, text=True).stdout or '{}')
            fmt = j.get('format', {})
            rows.append({'bin': os.path.relpath(r, root), 'name': f,
                         'created': fmt.get('tags', {}).get('creation_time'),
                         'dur': float(fmt.get('duration', 0))})
    json.dump(rows, open(out, 'w'), indent=1)
    print(len(rows), 'clips')


def offset(times, ref, ref_start, ref_in, other, other_start, other_in):
    t = {r['name']: r['created'] for r in json.load(open(times))}
    ts = lambda n: dt.datetime.fromisoformat(t[n].replace('Z', '+00:00')).timestamp()
    real_gap = (float(other_start) - float(other_in)) - (float(ref_start) - float(ref_in))
    print(f'{other} clock offset vs {ref}: {ts(other) - ts(ref) - real_gap:+.2f} s')


if __name__ == '__main__':
    if sys.argv[1:2] == ['scan']:
        scan(*sys.argv[2:4])
    elif sys.argv[1:2] == ['offset']:
        offset(*sys.argv[2:9])
    else:
        print(__doc__); sys.exit(1)
