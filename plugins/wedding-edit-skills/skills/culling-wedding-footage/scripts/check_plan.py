"""Check a cull plan before building it.
python3 check_plan.py <plan.json> <inventory.json> [motion.json]

Reports per section: files kept / raw files, select lengths, and problems:
- a clip outside its file, a file from another moment
- colours: not a Premiere label, uncoloured (Iris), the same colour as the neighbouring section, or a habit
  colour broken (the house style file's colour_habits; defaults Groom Prep Tan, portraits Rose, Dancing
  Yellow, aerials Violet)
Warnings (not problems): more than one select from a file, and, with motion.json (file_motion.py), select edges
on a fast camera move (above 8 px/frame in the first or last 0.5 s; Dancing and First Dance excepted). The
reference editor's own cull had 45 such edges of about 500, so keep to roughly 1 in 10 and look at each one.
Exit 1 when there are problems.
"""
import json, os, statistics as st, sys
if len(sys.argv) < 3:
    sys.exit(__doc__)

plan, inv = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
mo = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
LABELS = {'Violet', 'Iris', 'Caribbean', 'Lavender', 'Cerulean', 'Forest', 'Rose', 'Mango', 'Purple', 'Blue', 'Teal',
          'Magenta', 'Tan', 'Green', 'Brown', 'Yellow'}
HABIT = {'groom prep': 'Tan', 'portraits': 'Rose', 'evening portraits': 'Rose', 'dancing': 'Yellow', 'aerial': 'Violet',
         'drone': 'Violet'}
# The editor's own habits: a ```json block with "colour_habits" in ~/.claude/wedding-edit-style.md
STYLE = os.path.expanduser('~/.claude/wedding-edit-style.md')
if os.path.exists(STYLE):
    for block in open(STYLE).read().split('```json')[1:]:
        j = json.loads(block.split('```')[0])
        if 'colour_habits' in j:
            HABIT = {k.lower(): v for k, v in j['colour_habits'].items()}
MOVING_OK = ('dancing', 'first dance')
moment = lambda p: inv[p].get('moment') or os.path.basename(os.path.dirname(p))
raw = {}
for p in inv:
    raw.setdefault(moment(p), []).append(p)
problems, warnings, edges = [], [], [0, 0]
for sq in plan['sequences']:
    print(f"== {sq['name']}")
    prev = None
    for sec in sq['sections']:
        name, col, clips = sec['name'], sec['colour'], sec['clips']
        tag = f"{sq['name']}/{name}"
        if col not in LABELS:
            problems.append(f'{tag}: {col!r} is not a Premiere label')
        if col == 'Iris':
            problems.append(f'{tag}: Iris is the uncoloured default; every section gets a colour')
        if prev and col == prev:
            problems.append(f'{tag}: same colour as the section before ({col})')
        want = HABIT.get(name.lower())
        if want and col != want:
            problems.append(f"{tag}: house-style colour for {name} is {want}")
        prev = col
        paths = [c['path'] for c in clips]
        for c in clips:
            p, a, b = c['path'], c['in'], c['out']
            if p not in inv:
                problems.append(f'{tag}: {os.path.basename(p)} not in the inventory'); continue
            if not 0 <= a < b <= inv[p]['dur'] + 0.05:
                problems.append(f"{tag}: {os.path.basename(p)} {a:.1f}-{b:.1f} outside the file (0-{inv[p]['dur']:.1f})")
            if moment(p) != name and name not in ('Aerial', 'Drone'):
                problems.append(f'{tag}: {os.path.basename(p)} belongs to {moment(p)}')
            s = mo.get(p)
            if s and not name.lower().startswith(MOVING_OK):
                for edge, lo, hi in (('opens', a, a + 0.5), ('closes', b - 0.5, b)):
                    pk = max((v for t, v in s if lo <= t < hi), default=0)
                    edges[1] += 1
                    if pk > 8:
                        edges[0] += 1
                        warnings.append(f'{tag}: {os.path.basename(p)} {edge} on a camera move ({pk:.0f} px/frame)')
        dups = {p for p in paths if paths.count(p) > 1}
        if dups:
            warnings.append(f"{tag}: more than one select from {', '.join(sorted(os.path.basename(p) for p in dups))}")
        lens = [c['out'] - c['in'] for c in clips]
        n_raw = len(raw.get(name, [])) or len(paths)
        print(f"  {name:24s} {col:9s} {len(set(paths)):3d}/{n_raw:<3d} files ({len(set(paths)) / n_raw:4.0%})  "
              f"median {st.median(lens) if lens else 0:4.1f}s  max {max(lens) if lens else 0:5.1f}s  total {sum(lens):5.0f}s")
print(f'{len(warnings)} warning(s); select edges on a camera move: {edges[0]} of {edges[1]}')
for w in warnings:
    print('  ' + w)
print(f'{len(problems)} problem(s)')
for p in problems:
    print('  ' + p)
sys.exit(1 if problems else 0)
