# Audio production and verification

The 18 recordings are newly rendered from the score events in `music/performances/`; they are not live performances or excerpts from existing recordings. Each score retains its written note placement, articulation, velocity and, where applicable, pedal or expression control. The renderer uses 48 kHz stereo, pays particular attention to same-key retriggers and release tails, and applies one linked gain adjustment per take (no dynamics compression or limiting). Browser audio is LAME variable-bitrate MP3 (quality 2). The optionally generated 24-bit FLACs are not shipped.

## Instrument credits

- **Piano:** [Salamander Grand Piano v3](https://github.com/sfzinstruments/SalamanderGrandPiano/tree/3382bf9496bba2486f5ab0de55a264d1dfc38404), recorded by Alexander Holm from a Yamaha C5 grand; the FLAC packaging/remap is by kinwie. [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/), full text in `licenses/Salamander.txt`. This project selects 12 of the bank’s 16 velocity layers. It extracts recorded attacks, resamples adjacent pitches, applies note and pedal releases, blends the stereo image, and adds a custom room response.
- **Orchestra:** [GeneralUser GS 2.0.3](https://www.schristiancollins.com/generaluser.php) by S. Christian Collins, pinned source commit `684543d5e5efaef08d02be50dcda8d552478fa60`. The GeneralUser GS 2.0 license permits use in music production and release of musical recordings; see `licenses/GeneralUser-GS.txt`. Its author notes that some raw samples' individual provenance is incomplete. The SoundFont SHA-256 is `9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe`. FluidSynth renders the parts with authored stereo placement, expression and reverb.
- Raw instruments are downloaded for production and are not included in the website or its public source assets.

## Rebuild

From the repository root, with Python 3.11+, NumPy, SciPy, FFmpeg with libmp3lame and ffprobe, libsndfile, and FluidSynth available:

```sh
python scripts/render_audio.py --prefetch
python scripts/render_audio.py --offline
python scripts/verify_audio.py
```

The first line downloads only piano samples used in these scores and the pinned SoundFont, under `.cache/`. Omit `--prefetch` and `--offline` to download missing assets and render in one step. Use `--lossless` to retain optional 24-bit masters in `.cache/masters/`. Use positional score names for a focused render. Exact encoded bytes are expected to vary with the system's synth, numeric and codec versions.

`qa/audio-report.json` contains the score SHA-256, final MP3 SHA-256, codec/sample rate/channel count, duration, loudness, true peak and -45 dBFS bounds of decoded PCM per track, plus upstream sample digests. Passing checks establish technical correctness; they don't establish subjective timbre or live-performance realism. No subjective listening pass was performed by the audio renderer worker.
