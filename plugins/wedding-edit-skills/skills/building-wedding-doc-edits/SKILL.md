---
name: building-wedding-doc-edits
description: Use when building or replicating a wedding doc edit (documentary edit) in Adobe Premiere Pro through the Premiere MCP, cutting a stacked or synced first dance between two angles, or placing hundreds of trimmed stringout clips into a new Premiere sequence.
---

# Building wedding doc edits

A doc edit is the whole day in order, from culled **stringouts** (one sequence per part of the day, groups of selects separated by gaps). Build it by exporting the stringouts as FCP XML, reordering with `scripts/build_doc_edit.py`, and importing once. Look at footage through **source frames** pulled with ffmpeg: Premiere's own frame export renders black over this bridge.

Tools live in `${CLAUDE_SKILL_DIR}/scripts/`. Run each with `python3 -I <script>`, no arguments, for its usage. `${CLAUDE_SKILL_DIR}/plan.example.json` is a real running order.

## House style

Read `~/.claude/wedding-edit-style.md` before step 1. Its section order, first-dance pace and track layout override the defaults below. No file yet: tell the editor that the learning-edit-style skill can build one from a doc edit they have already cut. A reference doc edit from the editor (step 1) always wins over both.

## Steps

**1. Study the reference doc edit.** Export it to XML (step 5 mechanics) and run `frames.py sequence ref.xml sheet.jpg --tracks 1,2 --every 60`, reading the sheet. Delegate clip-by-clip paging (`get_sequence_structure`) to a subagent. Note per section: content, clip length, track roles (main cut on V1, cutaways and hole-fills on V2, adjustment layers, grain loop), and where music beds run with camera audio under them. *Done when* every section has a name and time range, and you can state what the reference leaves out. One reference left out the full ceremony and speeches, keeping only the signing and confetti exit.

**2. Settle scope with one AskUserQuestion**, recommended option first:
- First dance: stacked like the reference (you can do all of it), or a native multicam source sequence (the API cannot switch multicam angles, so the editor switches).
- Ceremony and speeches: left out like the reference, or included.
- Music: empty Music tracks plus a marker per section, or songs supplied.
- Grade and grain: copied, blank adjustment layer, or neither.

*Done when* all four are answered. Capture times give the order. Offer the day's schedule as a cross-check only.

**3. Order the day.**
- `capture_times.py scan` the media folder.
- Per camera body, get a clock offset from a synced stack (ceremony nest, stacked first dance) with `capture_times.py offset`.
- `build_doc_edit.py sections` lists each stringout's sections. It also lists clips on V2 and above, which need a `stacked` or `range` step.
- Write the plan JSON. `shell` names the stringout whose sequence settings the doc edit takes.

A camera is the file name minus its trailing digits (`A7S-9031` → `A7S-`). Each body needs its own prefix: rename the files when two bodies share one (`P1000123`).

Section ordering rules:
- Default `by_camera_time`: cameras merge by corrected time, each camera keeping the editor's order.
- Parallel storylines (bride and groom prep) use `interleave` with `min_run: 3`.
- Drone groups use `as_is`.
- Ceremony end is a `range` slice of the finished Ceremony cut, with overlay tracks. Find it with `get_sequence_structure` on the cut: it starts where the nested-multicam slices end and loose clips begin. XML export drops those nested slices, so an included full ceremony or speeches gets a marker, and the editor drops the finished cut in as a nest.

*Done when* two independent synced pairs agree on each offset within 1 s, and every stringout section appears in the plan once or is dropped with a stated reason.

**4. Cut the first dance** (stacked branch).
1. `sync_offset.py` on both angles must match the stringout stack within one frame.
2. `frames.py media` both angles every 4 s (`--offset` for the later-starting angle) and note whip-pans, blocked frames and when guests join.
3. `detect_beats` on the base audio.

The **base angle** is the wider one: on V1 for the whole dance, with its audio as the continuous track. The close angle's **cut-ins** go on V2, on beats:
- Couple alone: alternate about every 10 s.
- Once guests join: the close angle usually stays on the couple, so cut-ins run longer and the base angle's guest shots sit between them for 3 to 8 s.

Every time in this step is in base-clip seconds: sheet the base with no offset, the cut-in angle with `--offset` set to its stack offset, and run beats on the base file. Subtract the base's in-point when the base clip is trimmed. Ranges go in `stacked.cut_in_ranges`. *Done when* every cut-in range lands on clean frames on the sheet.

For the native multicam branch, build the stacked angles in their own sequence the same way and hand it over for the editor to switch.

**5. Assemble.**
1. `create_bin` "Doc Edit - Claude vN".
2. For each source sequence: `set_active_sequence`, then `export_as_fcp_xml` into an existing folder. It exports the active sequence only.
3. `build_doc_edit.py build plan.json` (it asserts no overlaps).
4. `import_fcp_xml` with `mode: into_open_project` and `target_bin` set to the new bin.
5. `add_markers_batch` from the sections JSON.
6. `add_tracks` audio 2, then `rename_track` to Music 1 and Music 2.

*Done when* `get_timeline_summary` per-track clip counts and duration equal the build's printout, and `get_offline_media` is empty.

**6. Verify and report.**
- `get_sequence_structure` on V2: the cut-ins sit at the planned times.
- `frames.py sequence built.xml sheet.jpg --every 75` reads in story order. Rename any marker the frames contradict.
- Report what differs from the stringouts (camera interleave, dropped fades) and that playback in Premiere is unchecked.
- Save only when asked.
- **Keep the plan** beside the wedding's project: copy the plan JSON to `<Edit folder>/Claude doc edit plan.json`
  and the built XML to `Claude doc edit.xml`. The editor edits the delivered sequence directly; later,
  `prproj_dump.py` (building-wedding-multicam) their edited sequence and compare it with the saved XML clip by
  clip (removed, added, re-trimmed, moved sections). Fold what you learn into their house style file.

## Gotchas

| Symptom | Fix |
|---|---|
| Frames from `export_frame` or review-frame tools are all black | `frames.py` from source media |
| Premiere stops answering after an XML export | Translation Report dialog (nested multicam clips are skipped). Ask the editor to click OK, or `request_access` Premiere and click OK with `app_screenshot` / `app_click` |
| `HOST_RECOVERY_REQUIRED` | `inspect_operation_recovery`, confirm the state, then `acknowledge_operation_recovery` with both revisions |
| Clip `start`/`end` of -1 in XML | Transition edges; the build tool rebuilds them and the cut becomes hard cuts |
| A finished cut has picture without linked sound | The `range` step takes camera audio in range and skips WAV recorders |
| Import adds a `<name>.prproj` sub-bin of duplicate clips | The new sequence uses them; keep it |
| Active sequence changes between calls | The editor is working too: build in a new bin, leave their sequences as they are, re-check the active sequence before export |
| zsh mangles `$n:l` in ffmpeg filters | Use `${n}`, or build the string in python |
| `add_to_timeline` places the wrong range | It uses project-item marks; use the XML route |
