#!/usr/bin/env python3
"""Shot-by-shot map of a finished ceremony/speeches cut: angle, hold, words under it.

  python3 shot_map.py <seq.json | seq.xml> <words.srt> <out_prefix> [--nest nest.json]
                      [--labels 0=A,1=B] [--remap /Volumes/HDD/=/Volumes/Edit/] [--sheet]

seq.json + --nest: a native multicam cut, both dumped by prproj_dump.py (angle = the nest's
video track index). seq.xml: a flattened cut exported as FCP XML (angle = camera folder name).
words.srt: word-level whisper SRT of what the cut sounds like, timeline-timed (mixdown.py).
Writes <out_prefix>.tsv (shot, start, end, dur, angle, words) and with --sheet contact sheets
<out_prefix>_NN.jpg of every shot's middle frame, pulled from the source file.
"""
import argparse, json, os, re, subprocess, sys, tempfile, urllib.parse
import xml.etree.ElementTree as ET

if len(sys.argv) == 1:
    sys.exit(__doc__)
p = argparse.ArgumentParser()
p.add_argument('seq'); p.add_argument('words'); p.add_argument('out')
p.add_argument('--nest'); p.add_argument('--labels', default=''); p.add_argument('--remap', default='')
p.add_argument('--sheet', action='store_true')
a = p.parse_args()
labels = dict(kv.split('=', 1) for kv in a.labels.split(',') if kv)
old, _, new = a.remap.partition('=')


def fix(path):
    path = urllib.parse.unquote(path or '').replace('file://', '')
    return path.replace(old, new, 1) if old else path


shots = []
if a.seq.endswith('.xml'):
    seq = ET.parse(a.seq).getroot().find('.//sequence')
    fps = int(seq.findtext('rate/timebase'))
    files = {f.get('id'): f.findtext('pathurl') for f in seq.iter('file') if f.find('pathurl') is not None}
    for c in seq.find('media/video/track').findall('clipitem'):  # V1 holds the cut
        st, en = int(c.findtext('start')), int(c.findtext('end'))
        if st < 0 or en < 0:  # transition edge; FCP XML stores the real edge on the transition
            continue
        path = fix(files.get(c.find('file').get('id')))
        shots.append(dict(start=st / fps, end=en / fps, angle=os.path.basename(os.path.dirname(path)),
                          path=path, src_in=int(c.findtext('in')) / fps))
else:
    seqj = json.load(open(a.seq))
    nest = json.load(open(a.nest)) if a.nest else {'tracks': []}
    angle_tracks = {t['index']: t['items'] for t in nest['tracks'] if t['type'] == 'video'}
    vtracks = [t for t in seqj['tracks'] if t['type'] == 'video']
    track = max(vtracks, key=lambda t: len(t['items']))
    for i in track['items']:
        if 'multicamAngle' not in i:
            if i.get('path'):
                shots.append(dict(start=i['start'], end=i['end'], angle='loose ' + os.path.basename(os.path.dirname(i['path'])),
                                  path=i['path'], src_in=i['in']))
            continue
        if shots and shots[-1]['angle'] == i['multicamAngle'] and abs(shots[-1]['end'] - i['start']) < 0.05:
            shots[-1]['end'] = i['end']  # same angle both sides of a razor: no visible switch
            continue
        nest_t = i['in']
        path, src_in = None, None
        for it in angle_tracks.get(i['multicamAngle'], []):
            if it['start'] <= nest_t + 0.5 * (i['end'] - i['start']) < it['end']:
                path, src_in = it['path'], it['in'] + (nest_t - it['start'])
        shots.append(dict(start=i['start'], end=i['end'], angle=i['multicamAngle'], path=path, src_in=src_in))

words = []
for b in open(a.words).read().strip().split('\n\n'):
    l = b.split('\n')
    ti = next((n for n, x in enumerate(l) if '-->' in x), None)
    if ti is None:
        continue
    t = [int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000 for h, m, s, ms in re.findall(r'(\d+):(\d+):(\d+),(\d+)', l[ti])]
    w = ' '.join(l[ti + 1:]).strip()
    if w and not w.startswith('['):
        words.append((t[0], t[1], w))

with open(a.out + '.tsv', 'w') as f:
    f.write('shot\tstart\tend\tdur\tangle\twords\n')
    for k, s in enumerate(shots):
        txt = ' '.join(w for ws, we, w in words if ws < s['end'] and we > s['start'])
        f.write(f"{k}\t{s['start']:.2f}\t{s['end']:.2f}\t{s['end'] - s['start']:.1f}\t{labels.get(str(s['angle']), s['angle'])}\t{txt}\n")
print(a.out + '.tsv', len(shots), 'shots')

if a.sheet:
    tmp, frames = tempfile.mkdtemp(prefix='shotmap-'), []
    for k, s in enumerate(shots):
        if not s['path']:
            continue
        lab = f"{k} {s['start']:.0f}s {labels.get(str(s['angle']), s['angle'])} {s['end'] - s['start']:.0f}s".replace(':', ' ').replace("'", '')
        out = f'{tmp}/{k:04d}.jpg'
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', f"{max(s['src_in'] + (s['end'] - s['start']) / 2, 0):.2f}",
                        '-i', s['path'], '-frames:v', '1', '-vf',
                        f"scale=320:-2,drawtext=text='{lab}':fontcolor=yellow:fontsize=14:x=4:y=4:box=1:boxcolor=black@0.6,format=yuvj420p", out])
        if os.path.exists(out):
            frames.append(out)
    for n in range(0, len(frames), 36):
        chunk = frames[n:n + 36]
        lay = '|'.join(f'{(i % 6) * 320}_{(i // 6) * 180}' for i in range(len(chunk)))
        sheet = f'{a.out}_{n // 36:02d}.jpg'
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', *sum((['-i', f] for f in chunk), []), '-filter_complex',
                        f'xstack=inputs={len(chunk)}:layout={lay}:fill=black', sheet], check=True)
        print(sheet, len(chunk))
