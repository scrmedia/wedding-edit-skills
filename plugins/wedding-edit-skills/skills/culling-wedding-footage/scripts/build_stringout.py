"""Build one stringout sequence per part of the day as FCP XML from a cull plan.
python3 build_stringout.py <plan.json> <out_dir> [--suffix " - Claude"] [--gap 2] [--fps 25]

plan.json: {"sequences": [{"name": "Morning", "sections": [{"name": "Bride Prep", "colour": "Rose",
            "clips": [{"path": ..., "in": s, "out": s}, ...]}, ...]}, ...]}
Clips run back to back on V1 in plan order; sections are separated by a gap. A clip with "track": 2 (or 3…)
is stacked above instead, starting "at" seconds after the start of the last V1 clip (other angles of the first
dance, synced by eye or by sound). Every clip (picture and sound)
carries its section's colour label. Camera sound: audio stream n of the file on audio track n (A7S: one
stereo stream; Panasonic: four mono streams).
"""
import argparse, json, os, subprocess, urllib.parse
import xml.etree.ElementTree as ET

ap = argparse.ArgumentParser()
ap.add_argument('plan'); ap.add_argument('out_dir')
ap.add_argument('--suffix', default=' - Claude'); ap.add_argument('--gap', type=float, default=2)
ap.add_argument('--fps', type=int, default=25)
a = ap.parse_args()
FPS = a.fps
COLOURS = ['Violet', 'Iris', 'Caribbean', 'Lavender', 'Cerulean', 'Forest', 'Rose', 'Mango', 'Purple', 'Blue',
           'Teal', 'Magenta', 'Tan', 'Green', 'Brown', 'Yellow']


def sub(p, tag, text=None, **attrs):
    e = ET.SubElement(p, tag, {k: str(v) for k, v in attrs.items()})
    if text is not None:
        e.text = str(text)
    return e


def rate(p, fps=FPS):
    r = sub(p, 'rate'); sub(r, 'timebase', fps); sub(r, 'ntsc', 'FALSE')


_probe = {}


def probe(path):
    if path not in _probe:
        j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
                                      capture_output=True, text=True, check=True).stdout)
        v = next(s for s in j['streams'] if s['codec_type'] == 'video')
        auds = [s for s in j['streams'] if s['codec_type'] == 'audio']
        tc = next((s['tags']['timecode'] for s in j['streams'] if s.get('tags', {}).get('timecode')), '00:00:00:00')
        _probe[path] = dict(dur=float(j['format']['duration']), v=v, streams=[int(x['channels']) for x in auds],
                            sr=int(auds[0]['sample_rate']) if auds else 48000, tc=tc, vfps=round(eval(v['r_frame_rate'])))
    return _probe[path]


def file_el(parent, path, ids):
    """<file> in full at first use in the document, then by id only (as build_multicam.py)."""
    if path in ids:
        sub(parent, 'file', id=ids[path]); return
    fid = ids[path] = f'file-{len(ids) + 1}'
    p = probe(path)
    f = sub(parent, 'file', id=fid)
    sub(f, 'name', os.path.basename(path)); sub(f, 'pathurl', 'file://localhost' + urllib.parse.quote(path))
    rate(f, p['vfps']); sub(f, 'duration', int(p['dur'] * p['vfps']))
    h, mi, se, fra = (int(x) for x in p['tc'].replace(';', ':').split(':'))
    tce = sub(f, 'timecode'); rate(tce, p['vfps'])  # Premiere opens nothing for a <file> without <timecode>
    sub(tce, 'string', p['tc']); sub(tce, 'frame', ((h * 60 + mi) * 60 + se) * p['vfps'] + fra); sub(tce, 'displayformat', 'NDF')
    m = sub(f, 'media')
    sc = sub(sub(m, 'video'), 'samplecharacteristics'); rate(sc, p['vfps'])
    sub(sc, 'width', p['v']['width']); sub(sc, 'height', p['v']['height'])
    sub(sc, 'anamorphic', 'FALSE'); sub(sc, 'pixelaspectratio', 'square'); sub(sc, 'fielddominance', 'none')
    for n, ch in enumerate(p['streams'], 1):
        au = sub(m, 'audio')
        asc = sub(au, 'samplecharacteristics'); sub(asc, 'depth', 16); sub(asc, 'samplerate', p['sr'])
        sub(au, 'channelcount', ch)
        if len(p['streams']) > 1:
            sub(sub(au, 'audiochannel'), 'sourcechannel', n)


def build(sq):
    name = sq['name'] + a.suffix
    root = ET.Element('xmeml', version='4')
    seq = sub(root, 'sequence', id='sequence-1'); sub(seq, 'name', name)
    dur_el = sub(seq, 'duration', 0); rate(seq)
    media = sub(seq, 'media'); vid = sub(media, 'video')
    first = probe(sq['sections'][0]['clips'][0]['path'])['v']
    fsc = sub(sub(vid, 'format'), 'samplecharacteristics'); rate(fsc)
    sub(fsc, 'width', first['width']); sub(fsc, 'height', first['height'])
    sub(fsc, 'anamorphic', 'FALSE'); sub(fsc, 'pixelaspectratio', 'square'); sub(fsc, 'fielddominance', 'none')
    vtrs = [sub(vid, 'track') for _ in range(max(c.get('track', 1) for s in sq['sections'] for c in s['clips']))]
    aud = sub(media, 'audio'); sub(aud, 'numOutputChannels', 2)  # an <audio> without <format> imports nothing
    asc = sub(sub(aud, 'format'), 'samplecharacteristics'); sub(asc, 'depth', 16); sub(asc, 'samplerate', 48000)
    n_tr = max(len(probe(c['path'])['streams']) for s in sq['sections'] for c in s['clips'])
    atr = [sub(aud, 'track') for _ in range(n_tr * len(vtrs))]  # a stacked angle's sound goes below V1's
    ids, cid, t, v1_start = {}, [0], 0, 0
    pos = {}  # clipitem id -> (media type, track no, index on track) for links

    def clipitem(track, path, st, en, src_in, colour, kind, tno):
        cid[0] += 1
        ci = sub(track, 'clipitem', id=f'clipitem-{cid[0]}')
        p = probe(path)
        sub(ci, 'name', os.path.basename(path)); sub(ci, 'enabled', 'TRUE')
        sub(ci, 'duration', int(p['dur'] * FPS)); rate(ci)
        sub(ci, 'start', st); sub(ci, 'end', en); sub(ci, 'in', src_in); sub(ci, 'out', src_in + en - st)
        file_el(ci, path, ids)
        if kind == 'audio':
            s = sub(ci, 'sourcetrack'); sub(s, 'mediatype', 'audio'); sub(s, 'trackindex', tno)
        sub(sub(ci, 'labels'), 'label2', colour)
        pos[ci.get('id')] = (kind, tno, len(track.findall('clipitem')))
        return ci

    for k, sec in enumerate(sq['sections']):
        assert sec['colour'] in COLOURS, f"{sec['name']}: colour {sec['colour']!r} is not a Premiere label"
        if k:
            t += round(a.gap * FPS)
        for c in sec['clips']:
            tn, src_in = c.get('track', 1), round(c['in'] * FPS)
            st = t if tn == 1 else v1_start + round(c.get('at', 0) * FPS)
            en = st + round(c['out'] * FPS) - src_in
            if tn == 1:
                v1_start = st
            group = [clipitem(vtrs[tn - 1], c['path'], st, en, src_in, sec['colour'], 'video', tn)]
            for n in range(len(probe(c['path'])['streams'])):
                an = (tn - 1) * n_tr + n
                group.append(clipitem(atr[an], c['path'], st, en, src_in, sec['colour'], 'audio', an + 1))
            for ci in group:  # picture and its sound move together
                for other in group:
                    kind, tno, idx = pos[other.get('id')]
                    lk = sub(ci, 'link'); sub(lk, 'linkclipref', other.get('id')); sub(lk, 'mediatype', kind)
                    sub(lk, 'trackindex', tno); sub(lk, 'clipindex', idx)
            t = max(t, en)
    dur_el.text = str(t)
    tc = sub(seq, 'timecode'); rate(tc); sub(tc, 'string', '00:00:00:00'); sub(tc, 'frame', 0); sub(tc, 'displayformat', 'NDF')
    ET.indent(root)
    out = os.path.join(a.out_dir, name + '.xml')
    with open(out, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding='unicode'))
    n = sum(len(s['clips']) for s in sq['sections'])
    print(f"{out}: {len(sq['sections'])} sections, {n} clips, {t / FPS:.1f} s")


os.makedirs(a.out_dir, exist_ok=True)
for sq in json.load(open(a.plan))['sequences']:
    build(sq)
