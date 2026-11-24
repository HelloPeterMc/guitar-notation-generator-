\version "2.24.0"
\header {
  title = "A Sunday Afternoon in Montmartre"
  tagline = ##f
}
\paper { #(set-paper-size "a4") }
\score {
  <<
    \new Staff = "melody" \with { instrumentName = "Melody" } {
      \clef treble \time 4/4
      \tempo 4 = 92
      e''2^\markup \column { \center-align "Em9" \fret-diagram-verbose #'( (place-fret 1 7) (place-fret 2 7) (place-fret 3 7) (place-fret 4 5) (place-fret 5 7) (mute 6) ) } g''2^\markup \column { \center-align "Cmaj7#11" \fret-diagram-verbose #'( (mute 1) (place-fret 2 7) (place-fret 3 9) (place-fret 4 9) (mute 5) (place-fret 6 8) ) } | fis''2^\markup \column { \center-align "Am9" \fret-diagram-verbose #'( (place-fret 1 7) (place-fret 2 5) (place-fret 3 5) (place-fret 4 5) (mute 5) (place-fret 6 5) ) } dis''2^\markup \column { \center-align "D13" \fret-diagram-verbose #'( (place-fret 1 7) (place-fret 2 7) (place-fret 3 5) (place-fret 4 4) (place-fret 5 5) (mute 6) ) } | g''2^\markup \column { \center-align "B7alt" \fret-diagram-verbose #'( (mute 1) (place-fret 2 8) (place-fret 3 8) (place-fret 4 7) (mute 5) (place-fret 6 7) ) } fis''2^\markup \column { \center-align "Em6" \fret-diagram-verbose #'( (mute 1) (place-fret 2 8) (place-fret 3 9) (place-fret 4 6) (place-fret 5 7) (mute 6) ) } | c''4^\markup \column { \center-align "Em6" \fret-diagram-verbose #'( (mute 1) (place-fret 2 8) (place-fret 3 9) (place-fret 4 6) (place-fret 5 7) (mute 6) ) } b'4 a'4 e'4 |
    }
    \new TabStaff = "guitar" \with { instrumentName = "Guitar" } {
      \clef moderntab \time 4/4
      <e'\2>2 <g'\2>2 | <fis'\2>2 <g'\2>2 | <g'\1>2 <fis'\1>2 | <c'\2>4 <b\2>4 <a\3>4 <e'\3>4 |
    }
  >>
  \layout { }
}
