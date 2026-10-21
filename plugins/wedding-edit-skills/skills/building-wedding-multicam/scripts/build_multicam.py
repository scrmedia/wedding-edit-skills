#!/usr/bin/env python3
"""Build a native-multicam ceremony/speeches sequence as FCP XML from a cut plan.

  python3 build_multicam.py <plan.json> <nest.json> <out.xml> [--name "Ceremony - Claude v1"] [--fps 25]
  python3 build_multicam.py check <plan.json> <dump.json>     (dump = prproj_dump.py of the imported sequence)

nest.json: prproj_dump.py of the synced multicam source (video track n = angle n, audio = lav WAVs).
plan.json (nest-time seconds):
  "video": [{"start", "end", "angle"}]          contiguous multicam cuts; the timeline starts at the first cut
  "audio": [{"mic": "<WAV stem, spaces as _>", "start", "end", "gain_db", "keyframes": [[nest_s, db]]}]
  "tail":  [{"file", "src_in", "dur", "track": 1|2|3, "start": s after the multicam, "audio": bool, "gain_db"}]
  "extra_sources": {"<name>": {"path", "offset"}}   recorders not in the nest (source time = nest time + offset)
  "fade_out_s": n
Picture is one FCP 7 <multiclip> (Premiere imports it as a real multicam nest): synced by <mediadelay>, the
full definition on the first cut only, later cuts reference the angle clips by id. Premiere ignores in-points
inside a multiclip, so every angle runs from its file's frame 0 and the nest starts with black on the
later-starting angles. Audio: each mic and the tail's camera sound on their own stereo track pair, levels as
Audio Levels (linear, 1.0 = 0 dB). The nest's grade (Lumetri per angle) and Premiere audio presets do not
travel through XML.
"""
import argparse, json, math, os, subprocess, sys, urllib.parse
import xml.etree.ElementTree as ET

if len(sys.argv) == 1:
    sys.exit(__doc__)


def sub(p, tag, text=None, **attrs):
    e = ET.SubElement(p, tag, {k: str(v) for k, v in attrs.items()})
    if text is not None:
        e.text = str(text)
    return e


def check(plan, dump):
    """Compare the imported sequence with the plan: picture cuts, angles, audio clip count."""
    plan, dump = json.load(open(plan)), json.load(open(dump))
    s0 = plan['video'][0]['start']
    mc = [i for t in dump['tracks'] if t['type'] == 'video' for i in t['items'] if 'multicamAngle' in i]
    bad = [(p['start'], p['angle'], d['start'], d.get('multicamAngle')) for p, d in zip(plan['video'], mc)
           if abs(p['start'] - s0 - d['start']) > 0.05 or p['angle'] != d['multicamAngle']]
    aud = sum(len(t['items']) for t in dump['tracks'] if t['type'] == 'audio')
    print(f"picture cuts: plan {len(plan['video'])}, imported {len(mc)}, mismatched {len(bad)} {bad[:5]}")
    print(f"audio clips imported: {aud} (stereo pairs may count once or twice)")
    return not bad and len(mc) == len(plan['video'])


if sys.argv[1] == 'check':
    sys.exit(0 if check(sys.argv[2], sys.argv[3]) else 1)

ap = argparse.ArgumentParser()
ap.add_argument('plan'); ap.add_argument('nest'); ap.add_argument('out')
ap.add_argument('--name', default='Ceremony - Claude'); ap.add_argument('--fps', type=int, default=25)
a = ap.parse_args()
plan, nest, FPS = json.load(open(a.plan)), json.load(open(a.nest)), a.fps


def fr(sec):
    return int(round(sec * FPS))


_probe = {}


def probe(path):
    if path not in _probe:
        j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
                                      capture_output=True, text=True, check=True).stdout)
        v = next((s for s in j['streams'] if s['codec_type'] == 'video'), None)
        auds = [s for s in j['streams'] if s['codec_type'] == 'audio']
        tc = next((s.get('tags', {}).get('timecode') for s in j['streams'] if s.get('tags', {}).get('timecode')), None)
        _probe[path] = dict(dur=float(j['format']['duration']), v=v, a=auds[0] if auds else None,
                            streams=[int(x['channels']) for x in auds], tc=tc or '00:00:00:00',
                            vfps=round(eval(v['r_frame_rate'])) if v else FPS,
                            ch=sum(int(x['channels']) for x in auds), sr=int(auds[0]['sample_rate']) if auds else 48000)
    return _probe[path]


_file_ids = {}


def file_el(parent, path):
    """<file> in full at first use, then by id only."""
    if path in _file_ids:
        sub(parent, 'file', id=_file_ids[path]); return
    fid = _file_ids[path] = f'file-{len(_file_ids) + 1}'
    p = probe(path)
    f = sub(parent, 'file', id=fid)
    sub(f, 'name', os.path.basename(path))
    sub(f, 'pathurl', 'file://localhost' + urllib.parse.quote(path))
    rate = sub(f, 'rate'); sub(rate, 'timebase', p['vfps']); sub(rate, 'ntsc', 'FALSE')
    sub(f, 'duration', int(p['dur'] * p['vfps']))
    # Premiere's import opens nothing for a <file> without <timecode>
    h, mi, se, fra = (int(x) for x in p['tc'].replace(';', ':').split(':'))
    tce = sub(f, 'timecode'); r = sub(tce, 'rate'); sub(r, 'timebase', p['vfps']); sub(r, 'ntsc', 'FALSE')
    sub(tce, 'string', p['tc']); sub(tce, 'frame', ((h * 60 + mi) * 60 + se) * p['vfps'] + fra); sub(tce, 'displayformat', 'NDF')
    m = sub(f, 'media')
    if p['v']:
        sc = sub(sub(m, 'video'), 'samplecharacteristics')
        r = sub(sc, 'rate'); sub(r, 'timebase', p['vfps']); sub(r, 'ntsc', 'FALSE')
        sub(sc, 'width', p['v']['width']); sub(sc, 'height', p['v']['height'])
        sub(sc, 'anamorphic', 'FALSE'); sub(sc, 'pixelaspectratio', 'square'); sub(sc, 'fielddominance', 'none')
    multi_mono = len(p['streams']) > 1
    for n, chans in enumerate(p['streams'], 1):  # one <audio> per stream, as Premiere exports multi-mono files
        au = sub(m, 'audio')
        sc = sub(au, 'samplecharacteristics'); sub(sc, 'depth', 16); sub(sc, 'samplerate', p['sr'])
        sub(au, 'channelcount', chans)
        if multi_mono:
            sub(sub(au, 'audiochannel'), 'sourcechannel', n)


def rate(p):
    r = sub(p, 'rate'); sub(r, 'timebase', FPS); sub(r, 'ntsc', 'FALSE')


ids = [0]


def clipitem(track, name, start, end, src_in, dur, **attrs):
    ids[0] += 1
    ci = sub(track, 'clipitem', id=f'clipitem-{ids[0]}', **attrs)
    sub(ci, 'name', name); sub(ci, 'enabled', 'TRUE'); sub(ci, 'duration', dur); rate(ci)
    sub(ci, 'start', start); sub(ci, 'end', end); sub(ci, 'in', src_in); sub(ci, 'out', src_in + end - start)
    return ci


def levels(ci, db, keyframes=(), src_offset=0.0):
    eff = sub(sub(ci, 'filter'), 'effect')
    sub(eff, 'name', 'Audio Levels'); sub(eff, 'effectid', 'audiolevels'); sub(eff, 'effectcategory', 'audiolevels')
    sub(eff, 'effecttype', 'audiolevels'); sub(eff, 'mediatype', 'audio')
    par = sub(eff, 'parameter', authoringApp='PremierePro')
    sub(par, 'parameterid', 'level'); sub(par, 'name', 'Level'); sub(par, 'valuemin', 0); sub(par, 'valuemax', 3.98109)
    sub(par, 'value', f'{10 ** (db / 20):.6f}')
    for t, kdb in keyframes:  # t in source seconds
        k = sub(par, 'keyframe'); sub(k, 'when', fr(t)); sub(k, 'value', f'{10 ** (kdb / 20):.6f}')


# ---- multiclip definition from the nest
angles = []
for t in sorted((t for t in nest['tracks'] if t['type'] == 'video'), key=lambda t: t['index']):
    paths = {i['path'] for i in t['items']}
    assert len(paths) == 1, f"angle {t['index']} uses several files {paths}: not supported yet"
    offs = {round(i['in'] - i['start'], 3) for i in t['items']}
    assert len(offs) == 1, f"angle {t['index']} items are not one continuous take"
    angles.append(dict(path=paths.pop(), off=offs.pop()))
M = max(an['off'] for an in angles)
for an in angles:
    an['delay'] = fr(M - an['off'])
    an['frames'] = fr(probe(an['path'])['dur'])
NEST_LEN = max(an['delay'] + an['frames'] for an in angles)
MC = a.name + ' MC'

root = ET.Element('xmeml', version='4')
seq = sub(root, 'sequence', id='sequence-1')
sub(seq, 'name', a.name)
dur_el = sub(seq, 'duration', 0)
rate(seq)
media = sub(seq, 'media')
vid = sub(media, 'video')
fsc = sub(sub(vid, 'format'), 'samplecharacteristics')
rate(fsc)
p0 = probe(angles[0]['path'])['v']
codec = sub(fsc, 'codec'); sub(codec, 'name', 'Apple ProRes 422')
asd = sub(codec, 'appspecificdata')
for tag, val in (('appname', 'Final Cut Pro'), ('appmanufacturer', 'Apple Inc.'), ('appversion', '7.0')):
    sub(asd, tag, val)
qt = sub(sub(asd, 'data'), 'qtcodec')
for tag, val in (('codecname', 'Apple ProRes 422'), ('codectypename', 'Apple ProRes 422'), ('codectypecode', 'apcn'),
                 ('codecvendorcode', 'appl'), ('spatialquality', 1024), ('temporalquality', 0), ('keyframerate', 0), ('datarate', 0)):
    sub(qt, tag, val)
sub(fsc, 'width', p0['width']); sub(fsc, 'height', p0['height'])
sub(fsc, 'anamorphic', 'FALSE'); sub(fsc, 'pixelaspectratio', 'square'); sub(fsc, 'fielddominance', 'none')
sub(fsc, 'colordepth', 24)
n_vtracks = max([1] + [t.get('track', 1) for t in plan.get('tail', [])])
vtracks = [sub(vid, 'track') for _ in range(n_vtracks)]

s0 = plan['video'][0]['start']
mc_end = 0
for k, c in enumerate(plan['video']):
    st, en = fr(c['start'] - s0), fr(c['end'] - s0)
    ci = clipitem(vtracks[0], MC, st, en, fr(c['start'] + M), NEST_LEN)
    mcel = sub(ci, 'multiclip', id='multiclip-1')
    sub(mcel, 'name', MC); sub(mcel, 'collapsed', 'FALSE'); sub(mcel, 'synctype', 1)  # on every cut, or nothing imports
    for n, an in enumerate(angles):
        ang = sub(mcel, 'angle')
        sub(ang, 'activevideoangle', 'TRUE' if n == c['angle'] else 'FALSE')
        sub(ang, 'activeaudioangle', 'FALSE')
        cl = sub(ang, 'clip', id=f'multiclip-1-angle-{n}')
        if k:
            continue
        sub(cl, 'name', os.path.basename(an['path'])); sub(cl, 'duration', NEST_LEN); rate(cl)
        inner = clipitem(sub(sub(sub(cl, 'media'), 'video'), 'track'), os.path.basename(an['path']),
                         0, an['frames'], 0, an['frames'])
        sub(inner, 'mediadelay', an['delay'])
        file_el(inner, an['path'])
    mc_end = en
end = mc_end

# ---- tail picture
for t in plan.get('tail', []):
    st = mc_end + fr(t['start'])
    ci = clipitem(vtracks[t.get('track', 1) - 1], os.path.basename(t['file']), st, st + fr(t['dur']), fr(t['src_in']),
                  fr(probe(t['file'])['dur']))
    file_el(ci, t['file'])
    end = max(end, st + fr(t['dur']))
if plan.get('fade_out_s'):
    tr = sub(vtracks[0], 'transitionitem')
    sub(tr, 'start', end - fr(plan['fade_out_s'])); sub(tr, 'end', end); sub(tr, 'alignment', 'end-black')
    ef = sub(tr, 'effect')
    for tag, val in (('name', 'Cross Dissolve'), ('effectid', 'Cross Dissolve'), ('effectcategory', 'Dissolve'),
                     ('effecttype', 'transition'), ('mediatype', 'video')):
        sub(ef, tag, val)

# ---- audio: one stereo pair (or mono track) per mic, then one for the tail's camera sound
aud = sub(media, 'audio')  # header as Premiere exports it; an <audio> without <format> imports nothing
sub(aud, 'numOutputChannels', 2)
asc = sub(sub(aud, 'format'), 'samplecharacteristics'); sub(asc, 'depth', 16); sub(asc, 'samplerate', 48000)
outs = sub(aud, 'outputs')
for n in (1, 2):
    g = sub(outs, 'group'); sub(g, 'index', n); sub(g, 'numchannels', 1); sub(g, 'downmix', 0); sub(sub(g, 'channel'), 'index', n)
mics = {os.path.splitext(os.path.basename(t['items'][0]['path']))[0].replace(' ', '_'): t['items'][0]
        for t in nest['tracks'] if t['type'] == 'audio' and t['items']}
for name, x in plan.get('extra_sources', {}).items():  # synced recorders outside the nest: source = nest t + offset
    mics[name] = {'path': x['path'], 'in': x['offset'], 'start': 0.0}
groups = []  # (name, path-for-channels, [(start, end, src_in_s, db, kf_src)])
for mic, it in mics.items():
    rows = []
    for x in plan.get('audio', []):
        if x['mic'] != mic:
            continue
        src = lambda nt, it=it: it['in'] + nt - it['start']
        rows.append((fr(x['start'] - s0), fr(x['end'] - s0), src(x['start']), x.get('gain_db', 0),
                     [(src(t), db) for t, db in x.get('keyframes', [])], it['path']))
    groups.append((mic, it['path'], rows))
cam = [(mc_end + fr(t['start']), mc_end + fr(t['start']) + fr(t['dur']), t['src_in'], t.get('gain_db', 0), [], t['file'])
       for t in plan.get('tail', []) if t.get('audio')]
groups.append(('tail camera sound', cam[0][5] if cam else None, cam))
unknown = {x['mic'] for x in plan.get('audio', [])} - set(mics)
assert not unknown, f'plan names mics not in the nest: {unknown}'

for name, path, rows in groups:
    if not rows:  # no empty tracks
        continue
    ch = 2 if not path or probe(path)['ch'] >= 2 else 1
    tracks = [sub(aud, 'track', premiereTrackType='Stereo' if ch == 2 else 'Mono',
                  currentExplodedTrackIndex=n, totalExplodedTrackCount=ch) for n in range(ch)]
    for st, en, src_in, db, kf, fpath in rows:
        pair = []
        for n, tr in enumerate(tracks):
            ci = clipitem(tr, os.path.basename(fpath), st, en, fr(src_in), fr(probe(fpath)['dur']),
                          premiereChannelType='stereo' if ch == 2 else 'mono')
            file_el(ci, fpath)
            st_el = sub(ci, 'sourcetrack'); sub(st_el, 'mediatype', 'audio'); sub(st_el, 'trackindex', n + 1)
            levels(ci, db, kf)
            pair.append(ci)
        if len(pair) == 2:  # link L and R (positional indexes filled below)
            for ci in pair:
                for other in pair:
                    lk = sub(ci, 'link'); sub(lk, 'linkclipref', other.get('id')); sub(lk, 'mediatype', 'audio')

# positional link indexes: trackindex = audio track number, clipindex = position on that track
pos = {}
for tn, tr in enumerate(aud.findall('track'), 1):
    for cn, ci in enumerate(tr.findall('clipitem'), 1):
        pos[ci.get('id')] = (tn, cn)
for ci in aud.iter('clipitem'):
    for lk in ci.findall('link'):
        tn, cn = pos[lk.findtext('linkclipref')]
        sub(lk, 'trackindex', tn); sub(lk, 'clipindex', cn); sub(lk, 'groupindex', 1)

dur_el.text = str(end)
tc = sub(seq, 'timecode'); rate(tc); sub(tc, 'string', '00:00:00:00'); sub(tc, 'frame', 0); sub(tc, 'displayformat', 'NDF')
ET.indent(root)
with open(a.out, 'w') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding='unicode'))
print(f"{a.out}: {len(plan['video'])} multicam cuts ({fr(plan['video'][-1]['end'] - s0) / FPS:.1f} s), "
      f"{len(plan.get('tail', []))} tail clips, {sum(len(r) for _, _, r in groups)} audio clips on "
      f"{len(aud.findall('track'))} tracks, {end / FPS:.1f} s total; nest {NEST_LEN / FPS:.1f} s, delays "
      + ', '.join(f"{os.path.basename(x['path'])} {x['delay'] / FPS:.2f}s" for x in angles))
