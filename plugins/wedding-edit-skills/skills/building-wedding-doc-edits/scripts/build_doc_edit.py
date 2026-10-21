#!/usr/bin/env python3
"""Assemble a wedding doc edit as FCP XML from exported Premiere stringout sequences.

  python3 build_doc_edit.py sections <xml_dir> <Source> [<Source> ...]
      List each exported sequence's V1 sections (runs of clips split by gaps).
  python3 build_doc_edit.py build <plan.json>
      Write the doc-edit XML + a sections JSON (marker times). See plan.example.json.

Handles: -1 clip edges under transitions, unlinked picture/sound in finished cuts,
exploded stereo audio tracks, positional <link> indexes, file definitions at first use,
camera clock offsets, and a stacked two-angle cut (base angle on V1, cut-ins on V2).
"""
import xml.etree.ElementTree as ET, json, sys, os, re, copy, datetime as dt

TPS = 254016000000  # Premiere ticks per second


def camera(name):
    return re.sub(r'\d+$', '', os.path.splitext(name)[0])


class Source:
    def __init__(self, xml_dir, name, gap_frames):
        self.name, self.gap = name, gap_frames
        self.root = ET.parse(os.path.join(xml_dir, name + '.xml')).getroot()
        self.seq = self.root.find('.//sequence')
        self.by_id = {c.get('id'): c for c in self.seq.iter('clipitem')}
        self.files = {}
        for f in self.seq.iter('file'):
            if len(f):
                self.files.setdefault(f.get('id'), f)
        self.vtracks = [t.findall('clipitem') for t in self.seq.find('media/video').findall('track')]
        self.atracks = [t.findall('clipitem') for t in self.seq.find('media/audio').findall('track')]
        self._resolve_transition_edges()

    def _resolve_transition_edges(self):
        # FCP XML writes -1 for a clip edge under a transition; recover it from in/out.
        g = lambda c, k: int(c.findtext(k))
        def s(c, k, v): c.find(k).text = str(v)
        vids = [v for t in self.vtracks for v in t]
        for c in self.by_id.values():
            st, en, length = g(c, 'start'), g(c, 'end'), g(c, 'out') - g(c, 'in')
            if st == -1 and en != -1: s(c, 'start', en - length)
            elif en == -1 and st != -1: s(c, 'end', st + length)
            elif st == -1 and en == -1:
                v = next((self.by_id[l.findtext('linkclipref')] for l in c.findall('link')
                          if l.findtext('mediatype') == 'video'), None) or \
                    next((v for v in vids if v.findtext('name') == c.findtext('name')
                          and g(v, 'in') == g(c, 'in') and g(v, 'start') != -1), None)
                if v is not None:
                    start = g(v, 'start') + g(c, 'in') - g(v, 'in')
                    s(c, 'start', start); s(c, 'end', start + length)

    def linked_audio(self, v):
        ids = [l.findtext('linkclipref') for l in v.findall('link') if l.findtext('mediatype') == 'audio']
        return [self.by_id[i] for i in ids if i in self.by_id]

    def has_video(self, clip):
        f = self.files.get(clip.find('file').get('id'))
        return f is not None and f.find('media/video') is not None

    def sections(self):
        clips = self.vtracks[0]
        out = [[clips[0]]]
        for c in clips[1:]:
            new = int(c.findtext('start')) - int(out[-1][-1].findtext('end')) > self.gap
            (out.append([c]) if new else out[-1].append(c))
        return out


def cmd_sections(xml_dir, names):
    for n in names:
        s = Source(xml_dir, n, 0)
        fps = int(s.seq.findtext('rate/timebase'))
        s.gap = fps  # 1 s
        for i, sec in enumerate(s.sections()):
            cams = sorted({camera(c.findtext('name')) for c in sec})
            st, en = int(sec[0].findtext('start')) / fps, int(sec[-1].findtext('end')) / fps
            print(f'{n}[{i}] {st:.2f}-{en:.2f}s clips={len(sec)} cameras={cams} first={sec[0].findtext("name")}')
        for t, clips in enumerate(s.vtracks[1:], 2):
            for c in clips:  # sections read V1 only; these need a 'stacked' or 'range' step
                print(f'  V{t} {int(c.findtext("start")) / fps:.2f}-{int(c.findtext("end")) / fps:.2f}s {c.findtext("name")}')


def cmd_build(plan_path):
    P = json.load(open(plan_path))
    fps = P.get('fps', 25)
    gap = round(P.get('section_gap_seconds', 1.0) * fps)
    offsets = P.get('clock_offsets', {})
    times = {r['name']: r for r in json.load(open(P['capture_times']))} if P.get('capture_times') else {}
    srcs = {}
    def src(n):
        if n not in srcs: srcs[n] = Source(P['xml_dir'], n, gap)
        return srcs[n]

    untimed = set()
    def key(c):
        r = times.get(c.findtext('name'))
        if not r or not r.get('created'):
            untimed.add(c.findtext('name')); return float('inf')  # sorts last in its section
        t = dt.datetime.fromisoformat(r['created'].replace('Z', '+00:00')).timestamp()
        return t - offsets.get(camera(c.findtext('name')), 0) + int(c.findtext('in')) / fps

    def by_camera_time(clips):
        """Cameras interleave by corrected capture time; each camera keeps the editor's order."""
        q = {}
        for c in clips: q.setdefault(camera(c.findtext('name')), []).append(c)
        out = []
        while any(q.values()):
            out.append(min((x for x in q.values() if x), key=lambda x: key(x[0])).pop(0))
        return out

    def blocks(a, b, min_run):
        """Two parallel storylines (bride / groom prep): chronological, in blocks of >= min_run."""
        a, b, out, cur, run = by_camera_time(a), by_camera_time(b), [], None, 0
        while a or b:
            if not a: pick = b
            elif not b: pick = a
            elif cur is not None and cur and run < min_run: pick = cur
            else: pick = a if key(a[0]) <= key(b[0]) else b
            if pick is not cur: cur, run = pick, 0
            out.append(pick.pop(0)); run += 1
        return out

    vout, aout, placed_audio, uid = {}, {}, set(), [0]

    def audio_track(a):  # stereo L/R -> T1/T2; mono ch1 -> T1, chN -> T(N+1)
        ch = int(a.findtext('sourcetrack/trackindex'))
        return ch - 1 if a.get('premiereChannelType') == 'stereo' else (0 if ch == 1 else ch)

    def place(s, c, shift, track, kind, retime=None):
        n = copy.deepcopy(c); uid[0] += 1
        if retime:
            st, en, i, o = retime
            for k, v in (('start', st), ('end', en), ('in', i), ('out', o)): n.find(k).text = str(v)
            n.find('pproTicksIn').text, n.find('pproTicksOut').text = str(i * TPS // fps), str(o * TPS // fps)
        else:
            for k in ('start', 'end'): n.find(k).text = str(int(c.findtext(k)) + shift)
        (vout if kind == 'video' else aout).setdefault(track, []).append((n, s, c.get('id'), f'c{uid[0]}'))

    def place_unit(s, v, shift, vtrack=0, audio=True):
        place(s, v, shift, vtrack, 'video')
        if audio:
            for a in s.linked_audio(v):
                if (s.name, a.get('id')) not in placed_audio:
                    placed_audio.add((s.name, a.get('id')))
                    place(s, a, shift, audio_track(a), 'audio')

    def clamped(a, lo, hi):
        st, en, i = int(a.findtext('start')), int(a.findtext('end')), int(a.findtext('in'))
        if st >= lo and en <= hi: return a
        a = copy.deepcopy(a); cut = max(0, lo - st); en = min(en, hi)
        for k, v in (('start', st + cut), ('end', en), ('in', i + cut), ('out', i + cut + en - st - cut)):
            a.find(k).text = str(v)
        a.find('pproTicksIn').text = str(int(a.findtext('in')) * TPS // fps)
        a.find('pproTicksOut').text = str(int(a.findtext('out')) * TPS // fps)
        return a

    cursor, sections = 0, []
    for step in P['order']:
        s = src(step['source'])
        sections.append({'name': step['label'], 'start_seconds': cursor / fps})
        if 'range' in step:  # a slice of a finished cut, overlay tracks kept
            lo, hi = (round(x * fps) for x in step['range'])
            shift = cursor - lo
            tracks = step.get('video_tracks', [1])
            for out_t, t in enumerate(tracks):
                for c in s.vtracks[t - 1]:
                    if lo <= int(c.findtext('start')) < hi:
                        place_unit(s, c, shift, out_t, audio=(out_t == 0))
            if not any((s.name, a.get('id')) in placed_audio for t in s.atracks for a in t):
                # finished cuts often have picture and sound unlinked: take camera audio in range
                for t in s.atracks:
                    for a in t:
                        if s.has_video(a) and int(a.findtext('start')) < hi and int(a.findtext('end')) > lo:
                            place(s, clamped(a, lo, hi), shift, audio_track(a), 'audio')
            cursor += hi - lo
        elif 'stacked' in step:  # two synced angles: base on V1 with its audio, cut-ins on V2
            st = step['stacked']
            base = s.vtracks[st['base'][0] - 1][st['base'][1] - 1]
            cut = s.vtracks[st['cut_in'][0] - 1][st['cut_in'][1] - 1]
            b0 = int(base.findtext('start'))
            place_unit(s, base, cursor - b0)
            dur = int(base.findtext('end')) - b0
            for a_s, a_e in st['cut_in_ranges']:  # seconds from the base clip's start
                fs, fe = round(a_s * fps), min(round(a_e * fps), dur)
                i = int(cut.findtext('in')) + b0 + fs - int(cut.findtext('start'))
                assert int(cut.findtext('in')) <= i and i + fe - fs <= int(cut.findtext('out')), ('cut-in outside angle', a_s, a_e)
                place(s, cut, 0, 1, 'video', retime=(cursor + fs, cursor + fe, i, i + fe - fs))
            cursor += dur
        else:
            secs = s.sections()
            if 'interleave' in step:
                clips = blocks(secs[step['interleave'][0]], secs[step['interleave'][1]], step.get('min_run', 3))
            else:
                clips = secs[step['section']]
                if step.get('order', 'by_camera_time') == 'by_camera_time':
                    clips = by_camera_time(clips)
            for c in clips:
                c0 = int(c.findtext('start'))
                place_unit(s, c, cursor - c0)
                cursor += int(c.findtext('end')) - c0
        sections[-1]['end_seconds'] = cursor / fps

    # no overlaps on any track
    for kind, tracks in (('V', vout), ('A', aout)):
        for i, t in tracks.items():
            t.sort(key=lambda x: int(x[0].findtext('start')))
            for (p, *_), (q, *_) in zip(t, t[1:]):
                assert int(p.findtext('end')) <= int(q.findtext('start')), (kind, i + 1, p.findtext('name'), q.findtext('name'))

    nv, na = max(vout) + 1, max(aout) + 1
    vlist = [vout.get(i, []) for i in range(nv)]
    alist = [aout.get(i, []) for i in range(na)]
    idmap = {(s.name, old): new for tl in (vlist, alist) for t in tl for _, s, old, new in t}
    pos = {new: (ti + 1, ci + 1) for tl in (vlist, alist) for ti, t in enumerate(tl) for ci, (_, _, _, new) in enumerate(t)}
    file_ids, master_ids = {}, {}
    for tl in (vlist, alist):
        for t in tl:
            for n, s, old, new in t:
                n.set('id', new)
                for l in list(n.findall('link')):
                    ref = idmap.get((s.name, l.findtext('linkclipref')))
                    # dropped partner (cut-in audio) or a reused clipitem: unlink
                    if ref is None or (ref != new and l.findtext('linkclipref') == old):
                        n.remove(l); continue
                    l.find('linkclipref').text = ref
                    l.find('trackindex').text, l.find('clipindex').text = map(str, pos[ref])
                if len(n.findall('link')) == 1:
                    n.remove(n.find('link'))
                f = n.find('file'); at = list(n).index(f); full = s.files[f.get('id')]
                path = full.findtext('pathurl'); n.remove(f)
                if path not in file_ids:  # full definition at first use, bare refs after
                    file_ids[path] = f'file-{len(file_ids) + 1}'
                    nf = copy.deepcopy(full); nf.set('id', file_ids[path])
                else:
                    nf = ET.Element('file', id=file_ids[path])
                n.insert(at, nf)
                if n.find('masterclipid') is not None:
                    n.find('masterclipid').text = master_ids.setdefault(path, f'masterclip-{len(master_ids) + 1}')

    shell = src(P['shell'])
    doc = copy.deepcopy(shell.root); seq = doc.find('.//sequence')
    seq.find('name').text = P['name']
    if seq.find('uuid') is not None: seq.remove(seq.find('uuid'))
    seq.find('duration').text = str(cursor)
    for k in [k for k in seq.attrib if k.startswith(('MZ.EditLine', 'MZ.WorkOutPoint', 'Monitor.'))]:
        del seq.attrib[k]
    for kind, lists in (('video', vlist), ('audio', alist)):
        m = seq.find(f'media/{kind}'); tmpl = m.findall('track')
        for t in tmpl: m.remove(t)
        for i, items in enumerate(lists):  # Premiere stringout layout: A1 stereo L, A2 stereo R, A3+ mono
            t = copy.deepcopy(tmpl[min(i, len(tmpl) - 1)] if kind == 'audio' else tmpl[0])
            for c in t.findall('clipitem'): t.remove(c)
            for j, (n, *_) in enumerate(items): t.insert(j, n)
            m.append(t)
    ET.ElementTree(doc).write(P['out_xml'], encoding='UTF-8', xml_declaration=True)
    body = open(P['out_xml'], encoding='utf-8').read().replace('?>\n', '?>\n<!DOCTYPE xmeml>\n', 1)
    open(P['out_xml'], 'w', encoding='utf-8').write(body)
    json.dump(sections, open(P['out_sections'], 'w'), indent=1)
    print(f'{cursor / fps:.2f}s  video tracks {[len(t) for t in vlist]}  audio tracks {[len(t) for t in alist]}')
    for x in sections:
        print(f"{x['start_seconds']:8.2f}-{x['end_seconds']:8.2f}  {x['name']}")
    if untimed:
        print(f'WARNING: {len(untimed)} clips have no capture time and sit last in their section:', sorted(untimed)[:10])


if __name__ == '__main__':
    if sys.argv[1:2] == ['sections']:
        cmd_sections(sys.argv[2], sys.argv[3:])
    elif sys.argv[1:2] == ['build']:
        cmd_build(sys.argv[2])
    else:
        print(__doc__); sys.exit(1)
