# Another Can-Can

**One melody. Nine different worlds.**

A complete, self-contained listening room for Offenbach's *Galop infernal* and eight newly authored stylistic variations, each separately arranged for piano and orchestra. Eighteen unique, expressive digitally performed recordings, not effect presets and not recordings of live players.

The default opens on the recognizable Offenbach theme. The variations are inspired by Mozart, Bach, Beethoven, Rossini, Poulenc, Chopin, Liszt, and Tchaikovsky. They are not works by those composers. No themes by the eight namesakes are quoted; Poulenc is represented through broad stylistic characteristics only.

## Listen locally

```sh
python3 -m http.server 8080 --directory site
```

Open `http://localhost:8080`. A static server is required because the score data is fetched; opening `index.html` directly through `file://` is not supported. There are no npm dependencies, runtime APIs, CDNs, analytics, accounts, or autoplay.

## Features

- Eighteen included stereo MP3 performances, approximately 52–79 seconds each.
- Source-derived canonical melody, with a short runway, famous refrain, return and cadence.
- Eight distinct compositional plans: minuet, invention, motivic drama, theatrical crescendo, dry modern wit, nocturne, virtuoso transformation, and waltz.
- Phrase-shaped timing, deliberate accents, voice balance, articulations and piano pedaling.
- Multi-velocity Salamander sampled piano and GeneralUser GS sampled orchestral instruments.
- A score-field visualization driven by actual per-note timestamps, pitch, voice and velocity.
- Phrase cue jumps, scrubbing, volume, mute, whole-piece view, MIDI downloads and A/B pinning.
- Instrument switches preserve the cue and fractional position within that phrase. Composer switches match corresponding formal sections, **not literal identical bars**.
- Keyboard-operable controls, visible focus, reduced-motion handling, native range inputs, no autoplay, and responsive phone/tablet/desktop layouts.

## Build and test

Python 3.11+ and Node 20+ suffice for the site and score checks:

```sh
npm test
npm run build
```

`dist/` is a deployable static site. It uses relative asset paths and can be served at a domain root or under a repository subpath. No host is configured or enabled by this repository itself.

### Rebuild the music

```sh
python3 music/compose.py
python3 music/verify.py
```

The score generator uses Python's standard library and produces deterministic MIDI and JSON from the same authored note events. It includes a vendored CC0 MusicXML transcription of the public-domain historical theme, with provenance and checksums in [`music/PROVENANCE.md`](music/PROVENANCE.md).

### Rerender the recordings

Rendering needs Python with NumPy and SciPy, libsndfile, FluidSynth, and FFmpeg/ffprobe with libmp3lame. See [`qa/AUDIO.md`](qa/AUDIO.md).

```sh
python3 scripts/render_audio.py --prefetch
python3 scripts/render_audio.py --offline
python3 scripts/verify_audio.py
cp music/performances/*.json music/performances/*.mid site/data/
npm test
```

Pinned, hash-checked instrument downloads go only to ignored `.cache/`. Raw sample libraries and optional FLAC masters are not included in the repository. The recordings preserve expressive dynamics; they use a linked gain adjustment, not compression/limiting. Encoded MP3 bytes may change across synth/codec versions, even when the event score is identical.

## Where things live

| Path | Purpose |
|---|---|
| `site/` | Complete static listening experience and playable audio |
| `music/compose.py` | Editable composition and orchestration source |
| `music/performances/` | Eighteen MIDI and JSON score pairs |
| `music/PROVENANCE.md` | Canonical theme provenance and arrangement notes |
| `scripts/render_audio.py` | Reproducible sampled-instrument renderer |
| `tests/` | Phrase switching and catalogue tests |
| `qa/` | Render measurements and browser/technical verification notes |
| `licenses/` | Third-party instrument and font licenses |

## Credits and boundaries

- Original theme: Jacques Offenbach, public domain. Historical print: Heugel, c.1862, H.3781. Machine-readable edition: Noctave, CC0.
- Piano: Alexander Holm's Salamander Grand Piano v3, FLAC remap by kinwie, **CC BY 3.0**. The rendered piano audio carries this attribution. Twelve of its sixteen velocity layers are used by the included scores.
- Orchestra: S. Christian Collins' GeneralUser GS 2.0.3 under its included license. Its creator permits musical recordings and notes incomplete individual provenance for some raw samples. No raw SoundFont is redistributed here.
- Fonts: Libre Bodoni and Instrument Sans, SIL Open Font License, self-hosted.

The technical tests verify event alignment, distinct tracks, decoding, format, duration, signal level and playback behavior. They do not certify subjective realism or claim the performances are human. Full public-facing credits are in `site/credits.html`.

Repository publication is separate from live deployment. Use the actual verified host URL if deploying; the presence of this source does not imply GitHub Pages has been enabled.
