#!/usr/bin/env python3
"""Validate recorded audio and exact source bindings against renderer QA."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS = "offenbach mozart bach beethoven rossini poulenc chopin liszt tchaikovsky".split()
EXPECTED = {f"{i}-{m}" for i in IDS for m in ("piano", "orchestra")}

def digest(path):
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()

def main():
    report = json.loads((ROOT / "qa/audio-report.json").read_text())
    tracks = report["tracks"]
    assert set(tracks) == EXPECTED, "Missing or unexpected tracks in QA report"
    assert {p.stem for p in (ROOT/"site/audio").glob("*.mp3")} == EXPECTED
    assert len({t["sha256"] for t in tracks.values()}) == len(EXPECTED), "Duplicate audio"
    for key, take in tracks.items():
        score = ROOT / "music/performances" / f"{key}.json"
        path = ROOT / "site/audio" / f"{key}.mp3"
        assert take["sha256"] == digest(path) and take["score_sha256"] == digest(score), key
        assert take["codec_name"] == "mp3" and int(take["sample_rate"]) == 48000 and take["channels"] == 2, key
        assert abs(take["decoded_frames"] - take["frames"]) <= 1152, key
        assert 1.45 <= float(take["duration"]) - take["score_seconds"] <= 1.9, key
        assert 0 <= take["first_audible_s"] <= 0.8, key
        assert take["score_seconds"]-1.0 <= take["last_audible_s"] <= float(take["duration"]), key
        assert -6 <= take["true_peak_dbtp"] <= -1 and min(take["rms_dbfs"]) > -35, key
    print(f"PASS: {len(tracks)} unique 48 kHz stereo MP3s match all score and recording digests")
    for key in ("duration", "true_peak_dbtp", "integrated_lufs", "first_audible_s", "last_audible_s"):
        values = [float(t[key]) for t in tracks.values()]
        print(f"{key}: {min(values):.3f} to {max(values):.3f}")

if __name__ == "__main__":
    main()
