# Wedding edit house style

This file tells the wedding edit skills how you cut. It lives at `~/.claude/wedding-edit-style.md`, outside the
plugin, so updates never overwrite it. Anything written here overrides the skills' defaults. Anything left out
falls back to them.

You can edit it by hand. Or ask Claude to "learn my edit style" and point it at a wedding you've already cut.
It fills this in from your own edit.

The values below are the defaults: one UK wedding filmmaker's style, measured from two weddings shot on a Sony
A7S main camera with Panasonic second cameras.

## Culling

Stringouts: `Morning`, `Reception`, `Evening`, one section per moment folder in day order, a gap between
sections. Clips inside a section run in filename order.

| Moment | Clips kept | Typical select |
|---|---|---|
| Venue Est, Pre Ceremony, guests arriving | 10-55% (fewer when there are lots) | 2.5-4.5 s |
| Bride Prep, Groom Prep | 35-50% | 4.7 s |
| Ceremony Est, Group Photos, Breakfast Est | 45-75% | 3-4 s |
| Reception Guests, Portraits, Breakfast Guests | 30-80% | 4-6 s |
| Evening Portraits, first looks, Confetti | 30-40% | 6 s |
| Evening Guests, Dancing | 90-100% | 4.5-6 s |
| First dance | every angle, whole, stacked | whole |

Selects overall: median 4.6 s, most between 3 and 9 s. Trims: about 1.7 s off the start, 2.7 s off the end.

Habits:
- Prep is the morning around the couple, not the dressing itself.
- One angle per posed moment when several cameras covered it.
- Telephoto candids past soft shoulders are fine. A soft head hiding the subject for the whole clip isn't.
- Long takes get split at the hugs and kisses.

Colours (every section gets one, and neighbouring sections never share):

```json
{"colour_habits": {"Groom Prep": "Tan", "Portraits": "Rose", "Evening Portraits": "Rose", "Dancing": "Yellow", "Aerial": "Violet"}}
```

## Ceremony and speeches

- Ceremony: the camera facing whoever is speaking carries each section with longer holds. The other operated
  camera covers the listeners in shorter holds. The wide comes in at section changes, about 10% of the time.
  Average hold is 7-15 s.
- Processional: the fastest stretch, about 5 s shots. Always show the groom's face when he first sees the bride.
- Never show a camera repositioning.
- Audio: officiant mic and groom's lav open together all ceremony, the groom about 5 dB under. The bride isn't
  mic'd, so her vows come through the groom's lav, lifted only for her own written vows.
- Speeches: the handheld mic recording alone, at one level, when every speaker used it. The speaker's angle
  carries about two-thirds of each speech. Couple reactions run about 2 a minute, 5-7 s each.

## Doc edit

- The whole day in order, from the stringouts. Ceremony and speeches are left out apart from the signing and the
  confetti exit.
- First dance: the wider angle on V1 for the whole dance with its sound. The close angle cuts in on V2 on the
  beat, about every 10 s while the couple are alone and for longer once guests join.
