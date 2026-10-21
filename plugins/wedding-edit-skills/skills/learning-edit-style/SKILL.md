---
name: learning-edit-style
description: Use when setting up the wedding edit skills for a new editor, learning their culling, ceremony, speeches or doc-edit style from a wedding they have already edited, writing ~/.claude/wedding-edit-style.md, or blind-testing the skills against an editor's own past edit before using them on a live wedding.
---

# Learning an editor's style

The culling, multicam and doc-edit skills ship with one filmmaker's defaults. This skill replaces them with the
editor's own, measured from a wedding they have already edited, and saves the result to
`~/.claude/wedding-edit-style.md` (outside the plugin, so updates never overwrite it). Then it proves the result
with a blind test on that same wedding.

Scripts: `${CLAUDE_SKILL_DIR}/scripts/`. The template is `${CLAUDE_SKILL_DIR}/house-style.example.md`. The other
skills' scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/`.

## Steps

1. **Check the setup.** `check_setup.py`, then the NLE's MCP: `get_premiere_state` (Premiere), or the
   equivalent call for the editor's NLE. No MCP tools at all: point the editor at the README's "Connect your
   editing software" section and stop until they're connected. Fix anything marked `--` that the editor's jobs need. Culling and doc
   edits don't need whisper. *Done when* the script says ready and the MCP answers.
2. **Pick the reference wedding** with one AskUserQuestion: a wedding they edited themselves, with its saved
   project, its raw footage still reachable, and the sequences that show their style (the cull stringouts, the
   ceremony and speeches cuts, the doc edit). Ask which sequences are which. If the raw has gone back into
   camera folders since, `inventory.py <wedding folder> inventory.json --from-project <their .prproj>` recovers
   each clip's moment. Tell them it takes one to three hours, mostly in the background.
3. **Measure the cull.** `inventory.py` (culling skill) on the wedding folder (with `--from-project` if
   needed), then `cull_style.py <project>
   inventory.json style/`. It writes `their_plan.json` (their cull in plan form) and prints keep rates, select
   lengths, trims, colours and clip order per moment. Then look at what they kept against what they dropped:
   `cull_strips.py "inventory.json:<Moment>" style/selects.json sheets/<moment>` boxes their kept ranges in
   green. Read the sheets for each moment, or one subagent per part of the day, and note where their taste
   differs from the culling skill's rules. *Done when* every moment has a keep rate and a sentence on what they
   keep and drop.
4. **Measure ceremony and speeches** (if they gave you those cuts): `prproj_dump.py` the nest and the cut, then
   read shot lengths, angle shares and open mics per section the way `compare_cuts.py` reports them. Compare
   with the multicam skill's rules and note the differences.
5. **Measure the doc edit** (if they gave you one): the doc-edit skill's step 1, then note the section order,
   what it leaves out, and the first-dance pace.
6. **Write the house style.** Copy the template to `~/.claude/wedding-edit-style.md` and replace every value
   with what you measured. Keep their colours as the `colour_habits` JSON block (`check_plan.py` reads it).
   Leave out what you couldn't measure, so it falls back to the defaults. Show the editor the file and ask
   what's wrong. *Done when* they agree with it.
7. **Blind test one part of the day.** Give a subagent only the culling skill, the inventory and the raw media
   for one part (Reception is a good one: lots of moments). Its prompt must forbid reading `style/`, the
   project file and `their_plan.json`. It writes `blind_plan.json`. Score it:
   `compare_cull.py blind_plan.json style/selects.json inventory.json`. Recall well above chance on the
   portraits, guests and group photos, and ranges overlapping by 0.5 or more, means the style file works. Where
   it misses, find the pattern, add it to the house style file, and say so.
8. **Report and suggest an order.** Show the editor the measured style, the blind test numbers, and what to try
   first. Culling is the lowest risk and the quickest to check. Ceremony and speeches come next. The doc edit
   comes last, because it builds from the other two. Tell them that editing what the skills deliver and asking
   Claude to compare their changes is how the style file keeps improving.

## What the numbers mean

- **Recall**: the share of their kept clips the blind cull also kept. **Chance**: the share a random pick of the
  same size would get. Recall only means something next to chance: keeping everything scores 100%.
- **Overlap (IoU)**: how much the two selects from the same clip overlap. 0.6 is close; under 0.4 the in and
  out points need work.
- Candid moments (prep, guests) score lowest because many clips are equally good. Structured moments (dancing,
  portraits, group photos, key moments) score highest. In the default style's own tests, the blind cull was
  rated "80% of the way there" by its editor.
