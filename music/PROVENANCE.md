# The score

**Theme:** Jacques Offenbach (1819–1880), *Galop infernal* from *Orphée aux enfers* (1858), public-domain composition. The 1862 anonymous solo-piano reduction was published by Heugel et Cie., Paris (plate H.3781, no. 28, printed pp. 80–83). [Historic score and edition details at IMSLP](https://imslp.org/wiki/Orph%C3%A9e_aux_enfers_(Offenbach,_Jacques)); [BnF Gallica record](https://gallica.bnf.fr/ark:/12148/bpt6k1187743z).

`canonical.mxl` is [Noctave’s note-for-note MusicXML edition of that print](https://noctavepiano.com/partitions/offenbach-galop-infernal/), released [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its original SHA-256 is `0fa34dd552016a5703bc37fd6211c61c69a6f70601db4cadc00f0b45ad0308f4`. No recording or modern protected arrangement was copied. Piano cuts to measures 43–62, 47–61, and 63–116, taking the second ending on the repeat. The orchestra retains that outline and the melody pitches by class (with practical octave displacements), but assigns new wind and string colours, pizzicatos, bass doubles, and fanfare punctuation. These are excerpts/new performances, not audio recordings of the unabridged opera.

**Eight new variations:** No themes by Mozart, Bach, Beethoven, Rossini, Poulenc, Chopin, Liszt, or Tchaikovsky are quoted. The lines are transformations of the G-major refrain (printed edition's digital measures 47–54 and the alternate closing phrase), placed in independently authored plans of metre, key, harmony, texture, instrumental distribution and form. The attributions describe inspiration, not authorship. For the Poulenc variation, only broad traits (dry wit, added-note harmony, alternation between detached and lyrical texture) inform the score.

| Variation | Identity | Piano / orchestra |
|---|---|---|
| Mozart | Light C-major minuet with minor trio and delicate cadential ornaments | Bass-and-lift pattern / flute, oboe and pizzicato with wind replies |
| Bach | D-minor invention texture, contrasting entries, stretto-like close with a major third | Imitating lower voice / oboe-to-violin lead, cello-to-bassoon counter-line |
| Beethoven | Short repeated knocks, a broad relative-major answer and C-major coda | Low octaves and accent gaps / short string figures, clarinet episode and brass |
| Rossini | F-major theatre overture with quiet comic aside, layered crescendo and finale | Bass/offbeat drive / wind hand-offs and late brass, timpani and percussion |
| Poulenc | Dry D-major syncopations, added-sixth and seventh harmony against a lyric middle | Detached chord splashes / oboe, bassoon and pizzicato giving way to sustained strings |
| Chopin | F-minor nocturne, embellished lyric line and widened final cadence | Rolled bass, slight right-hand delay and pedaling / clarinet, strings and harp |
| Liszt | F♯-minor invocation and tremolo rise toward an F♯-major ending | Wide arpeggios, tremolo and octaves / cello lead, harp and brass-led close |
| Tchaikovsky | E♭-major ballroom waltz and C-minor episode | Weighted downbeat and lighter lifts / sweeping strings, clarinet, harp and horns |

## Rebuilding

```sh
python3 music/compose.py
python3 music/verify.py
```

`compose.py` uses only the Python standard library. It exports SMF format 1 and aligned JSON from the same ticks; the JSON includes time, duration, MIDI pitch, velocity, part, cue labels and playback-controller events. The score uses bar-level tempo curves, phrase-end expansion, per-voice dynamics and different articulation lengths, plus seeded small attack variation. Pedaling is authored by bar in the lyrical keyboard scores. It is computer-performed and not attributed to real players. Durations exclude any downstream reverb tail.
