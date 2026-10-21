"""Dump a sequence's tracks straight from a .prproj (gunzipped or gzipped).

python3 prproj_dump.py <project.prproj> <sequence name or uid> <out.json>

Reads what the MCP and FCP XML can't: the chosen multicam angle per cut
(SelectedTrackIndex = the nest's video track index), clip Volume levels and keyframes,
audio filter names (presets in brackets), clip colour labels. Times are seconds; keyframe times are SOURCE
media time (timeline = start + kf - in). Volume is stored as linear gain where
0.17783 = 0 dB, so dB = 20*log10(v) + 15. Read a copy of the saved project: unsaved
edits in Premiere are not in the file.
"""
import gzip, json, math, sys
import xml.etree.ElementTree as ET

TICKS = 254016000000
LABELS = ['Violet', 'Iris', 'Caribbean', 'Lavender', 'Cerulean', 'Forest', 'Rose', 'Mango', 'Purple', 'Blue',
          'Teal', 'Magenta', 'Tan', 'Green', 'Brown', 'Yellow']  # BE.Prefs.LabelColors.N


def load(path):
    with open(path, 'rb') as f:
        head = f.read(2)
    opener = gzip.open if head == b'\x1f\x8b' else open
    with opener(path, 'rb') as f:
        return ET.parse(f).getroot()


def main(prproj, want, out):
    root = load(prproj)
    byid = {e.attrib['ObjectID']: e for e in root if 'ObjectID' in e.attrib}
    byuid = {e.attrib['ObjectUID']: e for e in root if 'ObjectUID' in e.attrib}

    def ref(e):
        if e is None:
            return None
        r = e.attrib.get('ObjectRef') or e.attrib.get('ObjectURef')
        hit = byid.get(r)
        return hit if hit is not None else byuid.get(r)

    def sec(t):
        return round(int(t) / TICKS, 3) if t not in (None, '') else 0.0  # absent = 0

    def db(v):
        v = float(v)
        return round(20 * math.log10(v) + 15, 2) if v > 0 else -999

    seqs = [e for e in root if e.tag == 'Sequence']
    seq = next((s for s in seqs if s.attrib.get('ObjectUID') == want or s.findtext('Name') == want), None)
    if seq is None:
        sys.exit('no sequence %r; have: %s' % (want, sorted({s.findtext('Name') for s in seqs})))

    def source_info(clip):
        """clip = VideoClip/AudioClip element -> (kind, name/path, extra)."""
        c = clip.find('Clip')
        src = ref(c.find('Source'))
        info = {'clipIn': sec(c.findtext('InPoint')), 'clipOut': sec(c.findtext('OutPoint'))}
        if c.findtext('IsMulticam') == 'true':
            info['multicamAngle'] = int(c.findtext('SelectedTrackIndex', '-1'))
        lab = c.findtext('Node/Properties/asl.clip.label.name') or ''
        if lab.startswith('BE.Prefs.LabelColors.'):  # the clip's colour label
            info['label'] = LABELS[int(lab.rsplit('.', 1)[1])]
        if src is None:
            return info
        sq = src.find('.//SequenceSource/Sequence')
        if sq is not None:
            s = ref(sq)
            info['sourceSequence'] = s.findtext('Name') if s is not None else None
            return info
        media = ref(src.find('.//MediaSource/Media'))
        if media is not None:
            info['path'] = media.findtext('FilePath') or media.findtext('ActualMediaFilePath')
        return info

    def filters(item):
        comps = ref(item.find('./ClipTrackItem/ComponentOwner/Components'))
        res = []
        if comps is None:
            return res
        for c in comps.findall('.//Components/Component'):
            fc = ref(c)
            if fc is None:
                continue
            name = fc.findtext('FilterMatchName') or fc.tag
            disp = fc.findtext('.//DisplayName')
            if disp and (name == fc.tag or (len(name) == 36 and name.count('-') == 4)):  # GUID match name
                name = disp
            inst = fc.findtext('.//InstanceName')
            if inst:
                name += ' [%s]' % inst
            f = {'name': name}
            for p in fc.findall('.//Params/Param'):
                pp = ref(p)
                if pp is None:
                    continue
                pn = pp.findtext('Name')
                if name.startswith('Internal Volume') and pn == 'Level':
                    start = pp.findtext('StartKeyframe', '').split(',')
                    if pp.findtext('IsTimeVarying') == 'true' or pp.findtext('Keyframes'):
                        kfs = []
                        for k in (pp.findtext('Keyframes') or '').split(';'):
                            parts = k.split(',')
                            if len(parts) >= 2 and parts[0]:
                                kfs.append([sec(parts[0]), db(parts[1])])  # media time, dB
                        f['levelKeyframes'] = kfs
                    f['levelDb'] = db(start[1]) if len(start) > 1 else db(pp.findtext('CurrentValue') or 0.17782794)
                if name.startswith('Internal Volume') and pn == 'Mute':
                    f['muteParam'] = pp.findtext('CurrentValue')
            res.append(f)
        return res

    out_tracks = []
    for tg in seq.findall('./TrackGroups/TrackGroup'):
        g = ref(tg.find('Second'))
        kind = {'VideoTrackGroup': 'video', 'AudioTrackGroup': 'audio'}.get(g.tag)
        if not kind:
            continue
        for t in g.findall('./TrackGroup/Tracks/Track'):
            tr = ref(t)
            idx = int(t.attrib['Index'])
            items = []
            for ti in tr.findall('./ClipTrack/ClipItems/TrackItems/TrackItem'):
                it = ref(ti)
                cti = it.find('ClipTrackItem')
                sub = ref(cti.find('SubClip'))
                clip = ref(sub.find('Clip')) if sub is not None else None
                rec = {
                    'start': sec(cti.findtext('./TrackItem/Start')),
                    'end': sec(cti.findtext('./TrackItem/End')),
                    'name': sub.findtext('Name') if sub is not None else None,
                }
                if clip is not None:
                    rec.update(source_info(clip))
                    if rec.get('clipIn') is not None:
                        rec['in'] = rec['clipIn']
                if it.findtext('.//IsAdjustmentLayer') == 'true':
                    rec['adjustment'] = True
                if cti.findtext('IsMuted') == 'true':  # a disabled clip is stored as IsMuted
                    rec['disabled'] = True
                fl = filters(it)
                if kind == 'audio':
                    rec['filters'] = fl
                else:
                    extra = [f['name'] for f in fl]
                    if extra:
                        rec['filters'] = extra
                items.append(rec)
            items.sort(key=lambda r: r['start'])
            out_tracks.append({'type': kind, 'index': idx, 'items': items})

    data = {'name': seq.findtext('Name'), 'uid': seq.attrib.get('ObjectUID'), 'tracks': out_tracks}
    json.dump(data, open(out, 'w'), indent=1)
    for t in out_tracks:
        if t['items']:
            names = sorted({(i.get('name') or '?') for i in t['items']})
            print('%s %d: %d items  %s' % (t['type'], t['index'] + 1, len(t['items']), ', '.join(names)[:150]))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
