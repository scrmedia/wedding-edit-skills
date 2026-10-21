---
name: culling-wedding-footage
description: Use when culling a wedding's raw footage into selects in Adobe Premiere Pro, building Morning, Reception and Evening stringout sequences from moment folders, colour-labelling sections, or reading how a finished cull was made.
---

# Culling wedding footage

The editor culls every moment folder of a wedding (Bride Prep, Group Photos, Dancing…) into one **stringout per
part of the day**: `Morning`, `Reception`, `Evening`. A stringout is their selects back to back, one section per
moment in day order, each section's clips in its own colour. You build them to **80-90%**: the editor finishes
the cull. Ceremony and speeches are multicams (building-wedding-multicam), not culled here.

Scripts are in `${CLAUDE_SKILL_DIR}/scripts/`; run each with `python3 -I <script>` and no arguments for its
usage. `prproj_dump.py` is in `${CLAUDE_PLUGIN_ROOT}/skills/building-wedding-multicam/scripts/`.

## House style

Read `~/.claude/wedding-edit-style.md` before step 1. Its keep rates, select lengths, colours and habits override
the numbers below, which are one wedding filmmaker's defaults (two weddings studied, Sony A7S main camera,
Panasonic second cameras). No file yet: tell the editor that the learning-edit-style skill can build one from a
wedding they have already culled, then carry on with these defaults if they'd rather.

## Steps

1. **Inventory:** `inventory.py <wedding folder> inventory.json` lists every clip by part and moment
   (`Morning/<moment>`, `Reception/<moment>`, `Evening/<moment>`, top-level `Aerial`). If the raw sits in camera
   folders instead, build the same JSON with a `moment` field per file. *Done when* every moment has its files.
2. **Motion scan** in the background: `file_motion.py inventory.json motion.json --jobs 4` (camera shift every
   0.1 s; about 15 min per 250 clips; 10-bit H.264 decodes in software, slowly).
3. **Make the sheets** in one background run, moment after moment: `cull_strips.py
   "inventory.json:<Moment>" - sheets/<moment> --frames 8` (one row per clip, capture order, times on every
   frame; each sheet path prints as soon as it is written). Several runs on one drive at once slow every run to a
   crawl, so never run them in parallel.
4. **Cull each moment** as its sheets arrive: read every sheet, pull single frames with ffmpeg where a sheet
   can't settle a choice, and decide per clip: drop, or a select (in, out) by the rules below. Large weddings:
   one subagent per part of the day reading the sheets, each writing its own part of the plan.
5. **Write the plan** (`plan.json`): `{"sequences": [{"name": "Morning", "sections": [{"name": "Bride Prep",
   "colour": "Purple", "clips": [{"path", "in", "out"}]}]}]}`, seconds in source time, sections in day order,
   clips in filename order. Other angles of a whole key moment (the first dance) stack above it: add `"track": 2,
   "at": <seconds after the V1 clip's start>` to the clip, lined up by eye or by sound.
6. **Check:** `check_plan.py plan.json inventory.json motion.json`. *Done when* 0 problems, keep rates sit in
   the ranges below or you can say why, and every warning is a select you looked at and still want.
7. **Build and verify:** `build_stringout.py plan.json xml/` (one FCP XML per stringout) → `import_fcp_xml`
   `new_project` into a throwaway project → `save_project` it → `master_labels.py` and `prproj_dump.py` it
   (colours and clip count match the plan) → `close_project`.
8. **Deliver** into a "Claude" bin in the editor's project (`create_bin` only if missing): `import_fcp_xml`
   `into_open_project` with `target_bin`, one per stringout. Re-check `get_premiere_state` first: the editor may
   be working at the same time. Never save their project.
9. **Keep the plan** beside the wedding's project: `<Edit folder>/Claude cull plan.json`. The editor edits the
   delivered stringouts directly; later, `prproj_dump.py` their edited sequences and `compare_cull.py` against
   this plan show what they added, removed and re-trimmed. Fold what you learn into their house style file.
10. **Report** keep counts per section, judgement calls, and anything you couldn't see well enough to judge.

## What to keep

- **Faces and something happening:** a laugh, a hug, a reaction, hair and makeup close-ups. Candid beats posed.
- **Prep is the morning around the couple, not a dressing checklist.** Groom Prep: the groomsmen arriving and
  standing about, the venue coming alive (lawn games set up, the room, the building), casual laughs, one tie or
  buttonhole shot, the rings. Bride Prep: robes, details, hair and makeup, gifts, laughs, the bride walking out.
  Drop the dressing itself (bridesmaids being laced in, jackets going on, buttonholes being fitted), the
  photographer's posed set-ups, and a second take of a detail.
- **Clean details** (dress, shoes, rings, invitations, flowers, venue features): 2-4 s each, the sharpest take.
- **Establishing shots** of each location; in an empty venue shot, keep the moment something moves through
  (a mower, people walking in the background): that movement is the reason to keep it.
- **Aerials** only where the venue is clearly the subject; long head trims on reveals.
- **Key moments long or whole:** first dance (whole, every angle stacked), first look, the couple's entrance
  (every angle), confetti, fireworks, outfit change, a long hug: 15 s to the whole clip. The cake cut gets one
  angle, about 10 s.
- **Performers stay** (harpist, sax, DJ, drummer); staff serving drinks or laying tables go.
- **Other long takes: split at the peaks**, nearly always physical contact (a hug, kiss, dip, forehead touch):
  a 49 s smoke-bomb take gave 4 selects; a greeting line gave only its hugs.
- **Backs are fine when the movement is the point:** the groom leading the bride out, the couple walking away.
- Breakfast set-up: nearly every slider and detail shot, unless soft, hazy or cluttered with glassware. Group
  photos: one static wide of each posed line-up, about 4 s; a walk towards camera ends as the front row reaches
  the lens. Guest games: the doing (writing), not the holding or reading.
- **Dancing and evening guests: nearly everything** (88-100% of clips), movement and all.

## What to drop

- **Obstruction:** a soft head or shoulder covering about a third of the frame and hiding the subject for the
  whole clip. If it clears (the makeup artist's back moves away), keep the clear window instead. Soft foreground
  that *frames* the subject is fine, a soft arm at the edge is fine, and telephoto candids shot past shoulders
  and passers-by are routine keeps; trim only once the lens is fully blocked.
- **Duplicates:** several takes of one subject → keep one, the cleanest, tightest or most alive (the take where
  the handheld drift settles, the one with movement in it), never by position. Same moment on the main camera
  and a second camera: the main camera usually wins. Limit takes per moment: a clean beat still goes when the
  moment is already covered.
- **Other cameras on the same beat:** a portrait set-up or posed moment covered by two or three cameras is a
  duplicate too: keep the best angle (in one reference wedding, the slow-motion main camera only; all 17
  second-camera clips of the evening portraits dropped). Keep a second camera only when it shows different
  people (guests, dancing) or a different shot size (a wide and a medium of the same walk). Camera clocks
  disagree (by 2-7 minutes in the reference weddings): line them up on one moment both shot before deciding two
  clips are simultaneous.
- **Nothing happening:** busy wides with no subject, backs of heads, long locked-off wides.
- **Unflattering:** half-dressed or mid-change, wiping a nose, drinking from a can, looking into the lens.
- **Behind the scenes:** staff at work, the photographer's own staged set-ups during prep and at the ceremony
  arch (one at most). Group photos are different: one wide of each line-up.
- **Vertical clips** (camera turned on its side): nearly all dropped (7 of 8 in one wedding).
- **False starts:** a 1-3 s aborted take just before the full one.
- **Waiting and transitions:** subjects waiting for a set-up, walking between set-ups, guests sitting with
  nothing changing.
- Soft focus, washed-out or blown exposure, a camera wandering across most of the clip.

## Ranges

- **One select per clip** (a few long takes give 2-4), median about 5 s (p10 3 s, p90 9-15 s), about half the clip.
- **In:** when the action starts, the foreground has cleared and the camera has settled (head trims about
  1.7 s; 5-9 s on portraits, where the couple talks before the pose peaks, and on drone reveals). **Out:**
  before the subject turns away or leaves, a head, arm or passer-by comes in, someone takes a bite or a drink,
  or the camera moves off (tail trims about 2.7 s). Obstructions set the cut points more often than the
  camera. A camera move at an edge is a soft signal, not a rule: about 1 edge in 10 sits on one in a real cull.
- **Deliberate moves stay** (a tilt, a slide, a rack focus onto the couple); accidental ones (a whip, a reframe)
  go. A whip in the middle of a good clip: two selects either side of it.
- Portraits: the peak beat (the kiss, the laugh, the couple walking out of the smoke), after about 5 s of set-up.
  Dancing: short, like everything else (median 4.5-6 s), usually from the start of the clip to just before a
  back or a fan blocks the lens; whole only when the whole clip is one good moment.

## Keep rate guide (clips kept / clips)

| Moment | Rate |
|---|---|
| Venue Est, Pre Ceremony, Morning/Ceremony Guests | 10-55%: the low end when there are 25+ clips |
| Bride Prep, Groom Prep | 35-50% |
| Ceremony Est, Group Photos, Breakfast Est | 45-75% |
| Reception Guests, Portraits, Breakfast Guests | 30-80% |
| Evening Portraits, add-on activities (a tattoo artist, an illustrator), first looks, Confetti | about 30-40% |
| Evening Guests, Dancing, Fireworks, Outfit Change | 90-100% |

## Stringouts and colours

- `Morning`: aerials of the venue first, then Venue Est, Bride Prep, Groom Prep, guests, Ceremony Est,
  Pre Ceremony. `Reception`: aerials, Confetti, Reception Guests, Group Photos, Portraits, Breakfast Est,
  Breakfast Guests. `Evening`: First Dance, Evening Portraits, Evening Guests, Dancing. Any other moment goes
  where it happened in the day. A clip stays in its moment's section even if it looks misfiled. Inside a
  section, **filename order** (how the bin sorts), not capture time; now and then move one strong clip to open
  it (the bride with her grandmother opening Evening Guests).
- **Every section gets a colour; neighbouring sections never share one.** Default habits: **Groom Prep Tan,
  portraits Rose, Dancing Yellow, aerials Violet** (`check_plan.py` reads the editor's own from their house
  style file). Any other label otherwise, never Iris (the uncoloured default). Labels: Violet, Iris, Caribbean,
  Lavender, Cerulean, Forest, Rose, Mango, Purple, Blue, Teal, Magenta, Tan, Green, Brown, Yellow.
- Editors who colour by hand usually colour the clips' project items, so the bin shows the colour. The XML import
  brings its own coloured copies of the clips in the Claude bin; the editor's moment bins stay as they are.

## Gotchas

| Symptom | Fix |
|---|---|
| `import_fcp_xml` times out at 120 s | It often finished anyway: `get_premiere_state`, then `inspect_operation_recovery` and `acknowledge_operation_recovery` before the next call |
| Colours missing when reading a project | `prproj_dump.py` shows the timeline clip's label; a hand-applied colour is usually on the project item: `master_labels.py` |
| Filmstrips take minutes per moment | VideoToolbox decodes HEVC and 8-bit H.264; 10-bit H.264 is software-only (its decode errors in the log are harmless): one background run, never several at once |
