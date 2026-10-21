"""Mono 16 kHz mixdown of a prproj_dump.py JSON's audio tracks: what the cut sounds like,
timeline-timed, ready for whisper-cli.

  python3 mixdown.py <seq.json> <out.wav>      (clip levels applied; keyframes ignored)
"""
import json, subprocess, sys
if len(sys.argv) != 3:
    sys.exit(__doc__)
d = json.load(open(sys.argv[1]))
items = [i for t in d['tracks'] if t['type'] == 'audio' for i in t['items'] if i.get('path')]
args, chains = [], []
for k, i in enumerate(items):
    lvl = next((f.get('levelDb') for f in i.get('filters', []) if f['name'].startswith('Internal Volume')), 0) or 0
    dur = i['end'] - i['start']
    args += ['-ss', f"{i['in']:.3f}", '-t', f'{dur:.3f}', '-i', i['path']]
    chains.append(f"[{k}:a]aformat=channel_layouts=mono,aresample=16000,volume={lvl}dB,adelay={int(i['start']*1000)}:all=1[a{k}]")
mix = ''.join(f'[a{k}]' for k in range(len(items))) + f'amix=inputs={len(items)}:normalize=0[out]'
subprocess.run(['ffmpeg', '-v', 'error', '-y', *args, '-filter_complex', ';'.join(chains + [mix]),
                '-map', '[out]', '-ac', '1', '-ar', '16000', sys.argv[2]], check=True)
print(sys.argv[2], len(items), 'clips')
