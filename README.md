# Wedding edit skills for Claude Code

Three Claude Code skills that do the first pass of a wedding edit in Premiere Pro, plus one that teaches them
how you cut.

- Culling: turns each moment folder (Bride Prep, Group Photos, Dancing and so on) into Morning, Reception and
  Evening stringouts, with every section colour labelled.
- Ceremony and speeches: cuts a native multicam from your synced multicam source sequence, picking angles and
  the cleanest mic for whoever is talking.
- Doc edit: assembles the whole day in order from the stringouts, with a cut first dance.
- Learning your style: measures how you cut a wedding you've already finished, writes that down, then tests
  itself blind against your own edit.

None of this replaces you. The aim is to get you about 80% of the way, so you start from a decent cut and spend
your time on the last 20%. It never saves your project or touches your own sequences. Everything it builds
lands in a bin called "Claude".

The defaults come from one UK wedding filmmaker's edits. They are a starting point, and the learning skill
swaps them for yours.

## What you need

Claude Code, plus an MCP server that lets Claude drive your editing software:

| Editor | MCP server | Status |
|---|---|---|
| Premiere Pro | [premiere-pro-mcp](https://premiere-pro-mcp.com/) ([GitHub](https://github.com/leancoderkavy/premiere-pro-mcp)) | Tested |
| DaVinci Resolve | Resolve's built-in MCP | Should mostly work, untested |
| Final Cut Pro | [SpliceKit](https://splicekit.fcp.cafe) | Needs adapting |

The skills read Premiere project files and build their sequences as FCP7 XML. Premiere and Resolve both import
that XML. Final Cut doesn't (it uses FCPXML), so on Final Cut the build steps need rewriting before they'll run.

You also need:

- Python 3.9 or newer
- ffmpeg built with the vidstab filter (`brew install ffmpeg` on a Mac includes it)
- whisper.cpp and its `ggml-tiny.en.bin` model, but only for ceremonies and speeches. Put the model in
  `~/.cache/whisper/` or point `WHISPER_MODEL` at it.

A Mac helps. ffmpeg uses the Mac's hardware decoder for most camera files, which makes filmstrips and motion
scans several times faster.

## Connect your editing software

Do this once, before installing the skills. For Premiere Pro with premiere-pro-mcp, on the computer that runs
Premiere:

1. Install the server: `npm install -g premiere-pro-mcp` (needs Node.js).
2. Install its Premiere panel: `premiere-pro-mcp --install-cep`.
3. Add it to Claude Code: `claude mcp add --scope user premiere-pro -- premiere-pro-mcp`.
4. Restart Premiere, open a project, then open Window > Extensions > MCP for Adobe Premiere Pro.
5. Run `premiere-pro-mcp --doctor`. It reports anything that isn't connected.

Their [README](https://github.com/leancoderkavy/premiere-pro-mcp) covers other routes, including a Claude Desktop
bundle that doesn't need Node.js. Resolve and Final Cut users should follow their MCP's own setup.

## Install

In Claude Code:

```
/plugin marketplace add scrmedia/wedding-edit-skills
/plugin install wedding-edit-skills@wedding-edit-skills
```

Then start a new Claude Code session (or run `/reload-plugins`) so the skills load.

## First run

1. Ask Claude to "check my setup for the wedding edit skills". It runs a short script and reports anything
   missing.
2. Ask Claude to "learn my edit style" and name a wedding you've already culled and cut. It needs the saved
   project and the raw footage. It measures your keep rates, clip lengths, colours, pace and mic habits, shows
   you what it found, and saves it to `~/.claude/wedding-edit-style.md`. Then it re-culls part of that wedding
   blind and scores itself against what you actually kept.
3. Try culling first. It's the quickest to check and the least risky. Ceremony and speeches come next, then
   the doc edit, which builds on both.

Allow time. Learning your style or culling a full wedding takes one to three hours, nearly all of it running in
the background while Claude makes and reads filmstrips of every clip, so you can keep working in Premiere. Big
weddings also take a good share of your Claude plan's usage, because Claude looks at thousands of frames.

You can skip step 2 and use the defaults. Expect the cull to look like someone else's, because it is.

## How it expects your footage

Raw clips sorted into moment folders under the part of the day:

```
Wedding/
  Aerial/
  Morning/Bride Prep/, Morning/Groom Prep/, ...
  Reception/Group Photos/, Reception/Portraits/, ...
  Evening/First Dance/, Evening/Dancing/, ...
```

Sort a new wedding into these folders before culling. Which moment a clip belongs to is your call, so the
skills don't guess it.

Ceremony and speeches are cut from a multicam source sequence you've already synced in Premiere.

If an older wedding's footage has since gone back into camera folders (an archive drive, say), the learning skill
can still use it. It reads which moment each clip was in from your saved Premiere project and matches the files
by name.

## It gets better as you edit

Each skill saves its plan in your Edit folder (`Claude cull plan.json` and similar). Edit what Claude
delivered however you like, then ask Claude to compare your changes. It lists what you added, cut and re-trimmed,
and folds the patterns into your style file. Save your project first, because Claude reads the saved file.

## Updating

When a new version comes out, run `/plugin marketplace update`. Your style file lives outside the plugin, so
updates change the method and leave your preferences alone.

## What's in here

```
plugins/wedding-edit-skills/skills/
  culling-wedding-footage/      stringouts from moment folders
  building-wedding-multicam/    ceremony and speeches multicams
  building-wedding-doc-edits/   the whole day, in order
  learning-edit-style/          setup check, style file, blind test
```

Each skill is a `SKILL.md` and a `scripts/` folder. Read them and change anything that doesn't fit how you work.

## Licence

MIT. See `LICENSE`.
