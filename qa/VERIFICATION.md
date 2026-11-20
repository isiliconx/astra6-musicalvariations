# Verification record

## Automated checks

- Five Node tests pass: nine-composer / eighteen-score catalogue; cue-preserving piano/orchestra switches; safe cross-composer section matching; start/time handling; A/B first-motif roundtrip regression.
- The independent MIDI reader verifies all 11,425 note events, controller data, tempo-derived timing and canonical refrain pitches against the JSON scores.
- All thirty-six score exports reproduce byte-for-byte from a clean generation.
- Static packaging checks confirm local links, unique IDs, no autoplay, eighteen unique MP3s, and exact public copies of all MIDI/JSON sources.
- Audio QA binds every MP3 to its exact source score hash. All eighteen have stereo 48 kHz MP3 format, non-silent signals, valid tails and no clipping. Detailed measurements and source digests are in `audio-report.json`.
- The static build succeeds without network or third-party build packages. It contains 62 files.

## Browser exercise

Tested in the cloud Chromium browser using the locally served static site:

- All eighteen composer/instrument combinations were selected and actually entered playback. Each reported readyState 4, a finite expected duration and no HTML media error.
- Each recording was paused and changed to the next take. Composer, instrumentation, programme text, MIDI link, cues and score field followed the selection.
- Confirmed reload starts paused at time zero on Offenbach orchestra.
- Exercised phrase jumps, restart, keyboard End seeking, whole-piece view, mute, pin, A/B switching and comparison clearing.
- Caught and corrected an A/B edge case where the first motif's short lead-in could be mistaken for an untouched playhead. The regression has a permanent test.
- Repeated composer switches during active playback ended on the last chosen composer and instrument, still playing the correct file.
- Reviewed desktop layout and a 390-pixel iframe viewport (375 CSS-pixel inner viewport after desktop scrollbar). Confirmed no document-level horizontal overflow. Exercised phone-layout playback, pause, instrument switching, last-composer navigation and cue jumps.
- Console inspection showed browser-extension metadata errors, not application errors.

## Boundaries

The narrow-viewport check validates responsive CSS and controls, not a physical iPhone or Safari audio stack. Browser checks verify playback state, not subjective listening quality. This environment did not support audio input for a subjective listening pass. Technical validation does not certify that a sampled performance sounds human.

The compositions are short, complete listening studies, not full-length replicas of named composers' works. The canonical Offenbach performance is explicitly abridged. A/B switching is exact by cue within one arrangement; across composers it maps corresponding formal sections, not identical bars.

No account, secrets, external runtime service or raw instrument library is included. Repository publication and live hosting are distinct; no deployment is claimed by this report.
