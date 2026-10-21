"""Colour label of every media file's project item (master clip) in a .prproj.
python3 master_labels.py <project.prproj> <out.json>   -> {media path: colour or null}"""
import gzip, json, sys, xml.etree.ElementTree as ET
if len(sys.argv) < 3:
    sys.exit(__doc__)
LABELS = ['Violet', 'Iris', 'Caribbean', 'Lavender', 'Cerulean', 'Forest', 'Rose', 'Mango', 'Purple', 'Blue',
          'Teal', 'Magenta', 'Tan', 'Green', 'Brown', 'Yellow']
f = open(sys.argv[1], 'rb'); gz = f.read(2) == b'\x1f\x8b'; f.close()
root = ET.parse(gzip.open(sys.argv[1]) if gz else sys.argv[1]).getroot()
byid = {e.attrib['ObjectID']: e for e in root if 'ObjectID' in e.attrib}
byuid = {e.attrib['ObjectUID']: e for e in root if 'ObjectUID' in e.attrib}
def ref(e):
    if e is None:
        return None
    r = byid.get(e.attrib.get('ObjectRef')) if 'ObjectRef' in e.attrib else byuid.get(e.attrib.get('ObjectURef')) if 'ObjectURef' in e.attrib else e
    return r
out = {}
for it in root.iter('ClipProjectItem'):
    lab = it.findtext('.//Column.PropertyText.Label') or ''
    mc = ref(it.find('.//MasterClip'))
    if mc is None:
        continue
    for c in mc.findall('.//Clips/Clip'):
        cc = ref(c)
        src = ref(cc.find('Clip/Source')) if cc is not None and cc.find('Clip/Source') is not None else None
        media = ref(src.find('.//MediaSource/Media')) if src is not None else None
        if media is not None:
            p = media.findtext('FilePath') or media.findtext('ActualMediaFilePath')
            if p:
                out[p] = LABELS[int(lab.rsplit('.', 1)[1])] if lab.startswith('BE.Prefs.LabelColors.') else None
                break
json.dump(out, open(sys.argv[2], 'w'), indent=0)
print(len(out), 'media items')
