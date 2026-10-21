"""Check this machine has what the wedding edit skills need, before the first real job.
python3 check_setup.py

Checks Python, ffmpeg and ffprobe, ffmpeg's vidstab filter (camera-motion scans), hardware decoding (macOS
VideoToolbox), whisper-cli and its model (ceremony and speeches transcripts), and a house style file. The NLE's
MCP server can't be checked from here: Claude checks it with the MCP's own ping or state call.
"""
import os, platform, shutil, subprocess, sys

ok = True


def line(good, what, fix=''):
    global ok
    ok &= good or fix.startswith('optional')
    print(('  ok   ' if good else '  --   ') + what + ('' if good else f'  ->  {fix}'))


def run(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout
    except OSError:
        return ''


line(sys.version_info >= (3, 9), f'Python {platform.python_version()}', 'install Python 3.9 or newer')
for tool in ('ffmpeg', 'ffprobe'):
    line(bool(shutil.which(tool)), tool, 'install ffmpeg (macOS: brew install ffmpeg)')
filters = run('ffmpeg', '-hide_banner', '-filters')
line('vidstabdetect' in filters, 'ffmpeg vidstab filter (camera-motion scans)',
     'install an ffmpeg built with libvidstab (Homebrew\'s ffmpeg has it)')
hw = run('ffmpeg', '-hide_banner', '-hwaccels')
line('videotoolbox' in hw, 'hardware decoding (VideoToolbox)',
     'optional: without it filmstrips and motion scans decode in software, several times slower')
line(bool(shutil.which('whisper-cli')), 'whisper-cli (ceremony and speeches transcripts)',
     'optional for culling and doc edits; for multicams: brew install whisper-cpp')
model = os.environ.get('WHISPER_MODEL') or os.path.expanduser('~/.cache/whisper/ggml-tiny.en.bin')
line(os.path.exists(model), f'whisper model {model}',
     'optional for culling and doc edits; download ggml-tiny.en.bin from huggingface.co/ggerganov/whisper.cpp '
     'into ~/.cache/whisper/ or set WHISPER_MODEL')
style = os.path.expanduser('~/.claude/wedding-edit-style.md')
line(os.path.exists(style), f'house style {style}',
     'optional: ask Claude to "learn my edit style" from a wedding you have already cut; until then the '
     'skills use their defaults')
print('\nready' if ok else '\nfix the lines marked -- above')
sys.exit(0 if ok else 1)
