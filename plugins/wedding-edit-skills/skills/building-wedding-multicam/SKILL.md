---
name: building-wedding-multicam
description: Use when cutting a wedding ceremony or speeches multicam in Adobe Premiere Pro through the Premiere MCP, building a multicam cut from a synced multicam source (nest) sequence, or reading how a finished multicam cut was switched.
---

# Building wedding multicams

The editor syncs each ceremony and speeches into a multicam source sequence, the **nest**. From it you build a native multicam cut that they can re-switch, to **80-90%**: the editor finishes it. The API can't switch angles, but Premiere's FCP XML import turns a `<multiclip>` into a real multicam with the chosen angle on every cut, so the work is a cut **plan** in nest time that `scripts/build_multicam.py` turns into XML.

Scripts are in `${CLAUDE_SKILL_DIR}/scripts/`; run each with `python3 -I <script>` and no arguments for its usage. `frames.py` and `sync_offset.py` live in `${CLAUDE_PLUGIN_ROOT}/skills/building-wedding-doc-edits/scripts/`. The rules come from one filmmaker's finished cuts and blind test builds they reviewed at 90-95%.

## House style

Read `~/.claude/wedding-edit-style.md` before step 1. Its pace, camera roles and audio habits override the defaults below. No file yet: tell the editor that the learning-edit-style skill can build one from a ceremony or speeches they have already cut, then carry on with these defaults if they'd rather.

## Steps

1. **Read the nest.** Copy the saved `.prproj` and `prproj_dump.py` the nest (and any finished cut you're shown). Video track n is angle n; audio tracks are one lav WAV per person. *Done when* you know each angle's camera and each mic's person.
2. **Prepare sources** in the background:
   - Recorders outside the nest (the venue handheld): `sync_offset.py` against two nest lavs, with `max_lag` above the gap between the files' start times (the default 30 s is often too short); the offsets must agree within a frame. Write `extra_sources.json` (source time = nest time + offset).
   - `prep_sources.py` → per-source transcripts and RMS in nest time.
   - `motion_scan.py` → camera shift per angle every 0.1 s (about 25 s of decode per minute of 4K per angle).
3. **Survey the angles** with `frames.py media` (`--offset` = item start − in) every 10-20 s: what each operated camera frames when, the wide, blocked stretches. *Done when* each section has a speaker angle, a listener angle and a wide.
4. **Write the plan** (`build_multicam.py` with no args shows the schema) by the rules below. Real time: the multicam runs continuously from start to end.
5. **Check the plan:** contiguous cuts; average hold 7-15 s; every mic switch in a speech gap; `motion_scan.py check plan.json motion.json --threshold 8 --allow <processional>` reports 0, and every `--threshold 3` flag is a slow, deliberate move you can name; `plan_sheet.py` sheets reviewed, plus every processional shot by eye. *Done when* all pass.
6. **Build and verify:** `build_multicam.py` → `import_fcp_xml` `new_project` into a throwaway project → `open_project` it, `save_project`, `prproj_dump.py` it, `build_multicam.py check` → `close_project` without saving. *Done when* every cut's angle matches.
7. **Deliver** into a "Claude" bin in the editor's project (`create_bin` only if it's missing): `import_fcp_xml` `into_open_project` with `target_bin`. Cuts are named `<MC>[n]`, n = angle + 1, so `get_sequence_structure` confirms every angle without saving their project. Re-check `get_premiere_state` before each import: the editor may be working at the same time.
8. **Keep the plan** beside the wedding's project: `<Edit folder>/Claude ceremony plan.json` (or speeches), plus
   the nest's dump as `Claude ceremony nest.json`. The editor re-switches the delivered cut directly; later,
   `prproj_dump.py` their edited cut and `compare_cuts.py <plan> <their cut> <nest>` show which angles, cut
   points and mics they changed. Fold what you learn into their house style file.
9. **Report** what XML didn't carry (every effect on the nest's angle clips, such as Lumetri and Motion, and their audio presets), any judgement calls, and that playback is unwatched.

## Ceremony

- **Starts** at the call to stand; **ends** with the kiss and applause. Then a short tail from loose camera files: a few seconds of the signing, the confetti exit with camera sound, a fade to black.
- **Camera roles:** the angle facing whoever speaks carries the section with the longer holds; the other operated angle covers the listeners (the groom's face during the bride's vows) in shorter holds; the static wide comes in at section turns, about 10%. The two operated angles mostly alternate.
- **Processional:** the fastest stretch (about 5 s shots); the aisle camera only here, 2-3 s inserts. **The groom's face when he first sees the bride** is a key moment: hold his reaction.
- **Readings:** the angle that sees the reader carries it.
- **Kiss:** the angle that sees both faces, held, then quick shots of the guests clapping and the wide.

## Speeches

- **Starts** with the first words introducing the speeches; **ends** after the final toast and applause. Nothing removed between speakers.
- **Camera roles per speaker:** the angle that frames the speaker carries about two-thirds to three-quarters of each speech; the other operated angle stays on the couple for reaction inserts (about 2 a minute, 5-7 s, on punchlines and sincere moments); the room wide for intros, getting up, big laughs and applause.
- **Hold to the speech:** sincere speeches hold the speaker around 15 s; in joke-heavy ones the room wide takes the big laughs, held about 8 s.
- **Toasts:** about 5 s shots, the wide, a short shot of the couple raising glasses.

## Audio

Lav and recorder WAVs on their own tracks; camera sound only for the ceremony tail.

| Situation | Default |
|---|---|
| Ceremony | Officiant mic and groom lav **open together** the whole ceremony (he prefers removing a mic to adding one); groom about 5 dB under. A reader's lav **alone** for their reading. |
| The bride (never mic'd) | Comes through the groom's lav. Lift it only for her own written vows; her "I do"s and repeats stay at the normal level. |
| Speeches | The handheld-mic recording alone, one continuous clip at **one flat level**, when every speaker used the handheld. Lavs only where it's missing. |
| Processional music | Whichever source is cleanest that day. |
| Switch points | In the gap at a hand-over, never mid-sentence. |

## Picture cuts

- **Cut on content and rhythm**: the audio runs underneath, so picture cuts land anywhere, mid-sentence included.
- **Cut away from a moving camera** and return only once it has settled. Fast moves (above 8 px/frame) never on screen; a slow push or follow onto the speaker is fine.

## Gotchas

| Symptom | Fix |
|---|---|
| `import_fcp_xml` "opened no new project", then `HOST_RECOVERY_REQUIRED` | The XML is off. `inspect_operation_recovery`, `acknowledge_operation_recovery`, then graft changes onto a known-good XML one at a time. `build_multicam.py` writes the known-good form |
| Multicam imported unsynced, every angle from frame 0 | Premiere ignores in-points inside a multiclip; sync is `<mediadelay>` (the builder does it) |
| One nest per cut | Full `<multiclip>` definition on the first cut only; later cuts reference angles by id, repeating name/collapsed/synctype |
| Per-second motion check passes a shot that opens mid-whip | Check at 0.1 s (`per_tenth`); `motion_scan.py check` does |
| Frames come out black | `frames.py` from source media, never Premiere's frame export |
| `get_clip_volume` etc. "clip not found" | They only see the active sequence; read the project file |
| Processional full of motion flags | Operators follow the walk on purpose; judge those shots by eye |
