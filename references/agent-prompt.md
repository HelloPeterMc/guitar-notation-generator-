# Prompt guide for guitar arrangements and lessons

Use this guide when an agent is asked to write guitar music or a practice lesson. The deliverable is a JSON score that the repository validator and renderers can process. A lesson does not need to be a song: use a descriptive title, section labels, and `notes` for teaching intent.

## Choose the task mode

- **Song or arrangement:** create a coherent piece with the requested form, harmony, melody, style, and guitar part.
- **Lesson plan:** create ordered exercises in score form. Put teaching sections in the optional bar-level `section` field. Explain the exercise goal, chord functions, position choices, and MIDI limitations in top-level `notes`.

In either mode, output one JSON object following `references/schema.json`. Do not output prose around the JSON when asked for the file itself.

## Core conventions

1. Pitches use sounding scientific notation (C4 is middle C). Never store the octave-shifted written guitar pitch.
2. Standard tuning is `E2 A2 D3 G3 B3 E4`, low to high, unless requested otherwise.
3. Tab strings are numbered 1 (high e) through 6 (low E); fret numbers are 0-24.
4. A chord `voicing` has six values, low E to high e. `-1` means muted and `0` means open.
5. Compute each fretted pitch as open-string pitch plus fret. Check every voicing against its chord name.
6. Every bar must add up exactly to the meter. In 6/8, for example, six eighth notes, three quarter notes, or two dotted-quarter notes each fill a bar.
7. Without `play_chord`, if both `melody` and `tab` are supplied, their sounding pitches must match. A melody-only event can omit tab; the renderer finds a playable position.
8. With `play_chord: true`, the guitar track and tab use the complete chord voicing. An optional `melody` is an independent guide line and may be a chord third or another note; omit `tab` on that event.
9. Use chord symbols the validator can interpret when possible. For a chord it cannot parse, validation warns rather than confirming the voicing.
10. Put assumptions and uncertainties in `notes`; do not present guesses as verified facts.

## Making a lesson plan

- Arrange exercises in the requested order and add a `section` label to the first bar of each section. Keep the same label on following bars if needed, or leave it off until the next section.
- For shell-voicing lessons, use three-note root/third/seventh shapes and check the actual pitches. Put the requested bass root on the requested string; do not assume a familiar shape has the intended bass.
- To practice a melody target over a strummed shell, set the chord and `play_chord: true`, then put the target note in `melody`. This can differ from the voicing's top note. The score's melody staff and MIDI guide use that explicit note; the guitar tablature and guitar MIDI track play the full voicing.
- Make each beat or subdivision an event when the melody changes. Keep durations exact. For example, a 6/8 bar can start with a dotted-quarter chord (`"4."`) and use three eighth-note melody events for the remaining half of the bar.
- Show ninths, thirteenths, and other extensions with voicings that contain those notes. Use a short event for each chromatic passing chord and verify that the bar still fills correctly.
- A `section` label and `notes` describe the lesson to the reader. The MIDI file contains the playable notes and generated accompaniment, not spoken instructions or teaching annotations.

## Before rendering

- Check the chord tones and bass note of every voicing.
- Confirm that melody and tab agree on ordinary melody events, and that independent melodies on `play_chord` events are playable.
- Add every event duration in each bar and confirm it equals the meter.
- Validate the JSON; fix musical errors rather than deleting data to make validation pass.

The generated MIDI has seven tracks: melody guide, guitar, keys, bass, horns, strings, and drums. Its backing arrangement is algorithmic and intended for practice; listen to it and revise the JSON if its voicings or style do not suit the lesson.
