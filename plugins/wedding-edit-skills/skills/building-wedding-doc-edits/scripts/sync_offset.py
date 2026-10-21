#!/usr/bin/env python3
"""How many seconds after <ref> the <other> recording starts, by audio cross-correlation.

  python3 sync_offset.py <ref_media> <other_media> [max_lag_seconds=30]

Pure python (no numpy): 50 Hz RMS envelopes for the coarse search, 500 Hz to refine.
Use it to confirm a stacked first dance is in sync before cutting it.
"""
import array, math, subprocess, sys


def envelope(path, hop):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-map', '0:a:0', '-ac', '1',
                          '-ar', '4000', '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    a = array.array('f'); a.frombytes(raw)
    out = [math.sqrt(sum(v * v for v in a[i:i + hop]) / hop) for i in range(0, len(a) - hop, hop)]
    m = sum(out) / len(out); sd = math.sqrt(sum((x - m) ** 2 for x in out) / len(out)) or 1
    return [(x - m) / sd for x in out]


def best(a, b, lags):
    def score(L):
        lo, hi = max(0, -L), min(len(b), len(a) - L)
        return sum(a[t + L] * b[t] for t in range(lo, hi)) / max(hi - lo, 1)
    return max((score(L), L) for L in lags)


if len(sys.argv) < 3:
    print(__doc__); sys.exit(1)
ref, other = sys.argv[1], sys.argv[2]
max_lag = float(sys.argv[3]) if len(sys.argv) > 3 else 30
s, L = best(envelope(ref, 80), envelope(other, 80), range(-int(max_lag * 50), int(max_lag * 50) + 1))
s2, L2 = best(envelope(ref, 8), envelope(other, 8), range(L * 10 - 30, L * 10 + 31))
print(f'other starts {L2 / 500:.3f} s after ref (coarse {L / 50:.2f} s, corr {s:.2f})')
