#!/usr/bin/env python3
"""Every audio source as 16 kHz mono in NEST time (t=0 = nest start), with whisper transcripts and RMS.

  python3 prep_sources.py <nest.json> <out_dir> [--extra extra_sources.json]

nest.json: prproj_dump.py of the synced multicam source; its audio tracks are the lav WAVs.
extra_sources.json: recorders not in the nest, {"<name>": {"path": "...", "offset": s}} with
source time = nest time + offset (find offset with sync_offset.py against two nest lavs; they must agree).
Writes <name>.wav, <name>_words.srt (word level, -ml 1 -sow), <name>_lines.srt, <name>_rms.json (dB per 0.5 s).
whisper tiny is good for content and who-speaks-when (word times ±0.3 s; names come out garbled).
Takes a few minutes per hour of audio; run it in the background.
"""
import json, os, re, subprocess, sys
if len(sys.argv) < 3:
    sys.exit(__doc__)
nest, out = json.load(open(sys.argv[1])), sys.argv[2]
os.makedirs(out, exist_ok=True)
# whisper.cpp model: set WHISPER_MODEL, or put ggml-tiny.en.bin in ~/.cache/whisper/
M = os.environ.get('WHISPER_MODEL') or os.path.expanduser('~/.cache/whisper/ggml-tiny.en.bin')
src = {}
for t in nest['tracks']:
    if t['type'] == 'audio' and t['items']:
        i = t['items'][0]
        src[os.path.splitext(os.path.basename(i['path']))[0].replace(' ', '_')] = (i['path'], i['in'] - i['start'], i['end'])
if '--extra' in sys.argv:
    for name, x in json.load(open(sys.argv[sys.argv.index('--extra') + 1])).items():
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                    x['path']], capture_output=True, text=True).stdout)
        src[name] = (x['path'], x['offset'], dur - x['offset'])
for name, (path, off, end) in src.items():
    wav = f'{out}/{name}.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(max(off, 0)), '-t', str(end), '-i', path,
                    '-ac', '1', '-ar', '16000', wav], check=True)
    for suffix, extra in (('words', ['-ml', '1', '-sow']), ('lines', [])):
        subprocess.run(['whisper-cli', '-m', M, '-f', wav, '-l', 'en', *extra, '-osrt', '-of', f'{out}/{name}_{suffix}'],
                       check=True, capture_output=True)
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', wav, '-af', 'asetnsamples=8000:p=0,astats=metadata=1:reset=1,'
                        'ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-', '-f', 'null', '-'],
                       capture_output=True, text=True)
    vals = [float(v) if v not in ('-inf', 'inf') else -120.0 for v in re.findall(r'RMS_level=(\S+)', r.stdout)]
    json.dump({'window_s': 0.5, 'rms_db': vals}, open(f'{out}/{name}_rms.json', 'w'))
    print('done', name, flush=True)
