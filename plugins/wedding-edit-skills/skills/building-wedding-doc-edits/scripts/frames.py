#!/usr/bin/env python3
"""Contact sheets from SOURCE media (Premiere's export_frame can return black frames via QE).

  python3 frames.py sequence <exported.xml> <out.jpg> [--every 60] [--tracks 1,2] [--start 0] [--end N]
      Frame of the top visible clip every N seconds of an FCP XML sequence, labelled time/track/file.
  python3 frames.py media <file> <out.jpg> --start S --end E --step N [--offset O]
      One file sampled at timeline times; the source time is t - O (for a synced angle).
"""
import argparse, os, subprocess, sys, tempfile, urllib.parse, xml.etree.ElementTree as ET

if len(sys.argv) == 1:
    print(__doc__); sys.exit(1)


def grab(path, src_t, label, out):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f'{max(src_t, 0):.2f}', '-i', path, '-frames:v', '1',
                    '-vf', f"scale=320:-2,drawtext=text='{label}':fontcolor=yellow:fontsize=14:x=4:y=4:box=1:boxcolor=black@0.6,format=yuvj420p",
                    out], check=True)


def tile(files, out, cols=6):
    files = [f for f in files if os.path.exists(f)]  # a time past the end of a file yields no frame
    args = sum((['-i', f] for f in files), [])
    lay = '|'.join(f'{(i % cols) * 320}_{(i // cols) * 180}' for i in range(len(files)))
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', *args, '-filter_complex',
                    f'xstack=inputs={len(files)}:layout={lay}:fill=black', out], check=True)
    print(out, len(files), 'frames')


p = argparse.ArgumentParser()
p.add_argument('mode', choices=['sequence', 'media']); p.add_argument('src'); p.add_argument('out')
p.add_argument('--every', type=float, default=60); p.add_argument('--tracks')
p.add_argument('--start', type=float, default=0); p.add_argument('--end', type=float)
p.add_argument('--step', type=float, default=4); p.add_argument('--offset', type=float, default=0)
a = p.parse_args()
tmp = tempfile.mkdtemp(prefix='frames-')
shots = []
if a.mode == 'sequence':
    seq = ET.parse(a.src).getroot().find('.//sequence')
    fps = int(seq.findtext('rate/timebase'))
    paths = {f.get('id'): urllib.parse.unquote(f.findtext('pathurl').replace('file://localhost', ''))
             for f in seq.iter('file') if f.findtext('pathurl')}
    want = {int(x) for x in a.tracks.split(',')} if a.tracks else None
    clips = []
    for ti, t in enumerate(seq.find('media/video').findall('track'), 1):
        if want and ti not in want: continue
        for c in t.findall('clipitem'):
            fid = c.find('file').get('id') if c.find('file') is not None else None
            if fid in paths and int(c.findtext('start')) >= 0:
                clips.append((ti, int(c.findtext('start')) / fps, int(c.findtext('end')) / fps,
                              int(c.findtext('in')) / fps, paths[fid], c.findtext('name')))
    end = a.end or max(c[2] for c in clips)
    t = a.start + a.every / 2
    while t < end:
        hit = sorted((c for c in clips if c[1] <= t < c[2]), key=lambda c: -c[0])
        if hit:
            ti, st, _, i, path, name = hit[0]
            out = os.path.join(tmp, f'{len(shots):03d}.jpg')
            grab(path, i + t - st, f'{int(t) // 60}m{int(t) % 60:02d} V{ti} {name}', out); shots.append(out)
        t += a.every
else:
    t = a.start
    while t <= a.end:
        out = os.path.join(tmp, f'{len(shots):03d}.jpg')
        grab(a.src, t - a.offset, f'{os.path.basename(a.src)} t={t:g}', out); shots.append(out)
        t += a.step
tile(shots, a.out)
