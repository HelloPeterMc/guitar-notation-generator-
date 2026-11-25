# Verified voicings

Every shape below passed `analyze_chord` (the name matches the sounding notes). Voicing arrays run low E to high e; `-1` = muted. Prefer these over inventing shapes; for any other shape, run `python -m guitar_notation check` before rendering.

| Chord | Voicing | Sounding notes (low to high) | Top note | Note |
|---|---|---|---|---|
| Em9 | `0 2 4 0 3 0` | E2 B2 F#3 G3 D4 E4 | E4 | open |
| Em9 | `x 7 5 7 7 7` | E3 G3 D4 F#4 B4 | B4 | 7th position |
| Em6 | `0 2 2 0 2 0` | E2 B2 E3 G3 C#4 E4 | E4 | open |
| Em6/9 | `0 2 2 0 2 2` | E2 B2 E3 G3 C#4 F#4 | F#4 | open |
| Em7 | `0 2 0 0 0 0` | E2 B2 D3 G3 B3 E4 | E4 | open |
| Em | `0 2 2 0 0 0` | E2 B2 E3 G3 B3 E4 | E4 | open |
| Cmaj7#11 | `8 x 9 9 7 x` | C3 B3 E4 F#4 | F#4 | 8th position, no 5th |
| Am9 | `5 x 5 5 5 7` | A2 G3 C4 E4 B4 | B4 | 5th position |
| Am7 | `x 0 2 0 1 0` | A2 E3 G3 C4 E4 | E4 | open |
| D13 | `x 5 4 5 7 7` | D3 F#3 C4 F#4 B4 | B4 | shell, no 5th |
| D7 | `x x 0 2 1 2` | D3 A3 C4 F#4 | F#4 | open |
| B7b13 | `7 x 7 8 8 x` | B2 A3 D#4 G4 | G4 | 7th position, no 5th |
| B7 | `x 2 1 2 0 2` | B2 D#3 A3 B3 F#4 | F#4 | open |
| Cmaj7 | `x 3 2 0 0 0` | C3 E3 G3 B3 E4 | E4 | open |
| Gmaj7 | `3 x 4 4 3 x` | G2 F#3 B3 D4 | D4 | 3rd position |
| Fmaj7 | `x x 3 2 1 0` | F3 A3 C4 E4 | E4 | open |

## Common mislabels

- `x 7 6 9 8 x` spells E G# E G. It is not Em6 (use `0 2 2 0 2 0`).
- `7 x 7 8 8 x` spells B A D# G: that is B7b13 (B7 with a flat 13th), not B7#9.
- `0 2 4 0 3 0` is a correct open Em9, and `0 2 2 0 2 0` is Em6 (not plain Em).
