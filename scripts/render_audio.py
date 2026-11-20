#!/usr/bin/env python3
"""Deterministic score-to-stereo audio production for the Can-Can listening room."""
import argparse
import concurrent.futures
import ctypes as C
import ctypes.util
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

import numpy as np
from scipy.signal import fftconvolve, resample_poly, butter, sosfilt

ROOT = Path(__file__).resolve().parents[1]
RATE = 48000
PIANO_TAIL = 1.5
ORCH_TAIL = 1.8
CACHE = ROOT / ".cache"
SALA = "https://raw.githubusercontent.com/sfzinstruments/SalamanderGrandPiano/3382bf9496bba2486f5ab0de55a264d1dfc38404/"
GS = "https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/684543d5e5efaef08d02be50dcda8d552478fa60/"
GS_HASH = "9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe"
FILE_LOCKS = {}
LOCKS_LOCK = threading.Lock()
LAYER_UPPER = (26,34,36,43,46,50,56,64,72,80,88,96,104,112,120,127)
DYNAMIC_LAYERS = (2,4,6,7,8,9,10,11,12,13,14,16)
NAMES = "C C# D D# E F F# G G# A A# B".split()


def fetch(base, name, target, *, offline=False, digest=None):
    with LOCKS_LOCK:
        lock = FILE_LOCKS.setdefault(target, threading.Lock())
    with lock:
        if target.exists():
            if not digest or sha(target) == digest:
                return target
            raise ValueError(f"SHA-256 mismatch in cached dependency: {target}")
        if offline:
            raise FileNotFoundError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + f".{os.getpid()}.partial")
        for attempt in range(4):
            try:
                with urlopen(Request(base + quote(name, safe="/"), headers={"User-Agent": "CanCan-Score-Audio/1.0"}), timeout=50) as src, temp.open("wb") as out:
                    shutil.copyfileobj(src, out)
                if digest and sha(temp) != digest:
                    raise ValueError(f"SHA-256 mismatch downloading {name}")
                if name.endswith(".flac"):
                    with temp.open("rb") as file:
                        if file.read(4) != b"fLaC":
                            raise ValueError(f"Not a FLAC: {name}")
                temp.replace(target)
                return target
            except Exception:
                temp.unlink(missing_ok=True)
                if attempt == 3:
                    raise
                time.sleep(.45 * 2 ** attempt)


@lru_cache(maxsize=2048)
def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pname(note):
    return NAMES[note % 12] + str(note // 12 - 1)


def key_center(note):
    return min(108, max(21, 3 * round(note / 3)))


def velocity_layer(vel):
    natural = int(np.searchsorted(LAYER_UPPER, int(vel), side="left")) + 1
    return min(DYNAMIC_LAYERS, key=lambda i: abs(i-natural))


def sample_name(note, vel):
    return f"{pname(key_center(note))}v{velocity_layer(vel)}.flac"


def sample_file(name, offline):
    return fetch(SALA, f"Samples/{name}", CACHE/"piano"/name, offline=offline)


def acquire(names, offline, n=14):
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        for _ in pool.map(lambda x: sample_file(x, offline), sorted(set(names))):
            pass


class SndInfo(C.Structure):
    _fields_ = [("frames", C.c_int64), ("samplerate", C.c_int), ("channels", C.c_int),
                ("format", C.c_int), ("sections", C.c_int), ("seekable", C.c_int)]


def lib(name):
    path = ctypes.util.find_library(name)
    if not path:
        raise RuntimeError(f"System library not found: {name}")
    return C.CDLL(path)


def signature(libobj, name, restype, *argtypes):
    fn = getattr(libobj, name)
    fn.argtypes, fn.restype = list(argtypes), restype
    return fn


@lru_cache(maxsize=1)
def snd():
    a = lib("sndfile")
    signature(a, "sf_open", C.c_void_p, C.c_char_p, C.c_int, C.POINTER(SndInfo))
    signature(a, "sf_readf_float", C.c_int64, C.c_void_p, C.c_void_p, C.c_int64)
    signature(a, "sf_close", C.c_int, C.c_void_p)
    return a


@lru_cache(maxsize=32)
def decode_sample(name, offline):
    a = snd()
    info = SndInfo()
    p = sample_file(name, offline)
    handle = a.sf_open(str(p).encode(), 0x10, C.byref(info))
    if not handle:
        raise ValueError(f"Unable to decode {p}")
    try:
        frames = min(info.frames, int(info.samplerate*8.1))
        mat = np.zeros((frames, info.channels), dtype=np.float32)
        if a.sf_readf_float(handle, mat.ctypes.data, frames) != frames:
            raise ValueError(f"Truncated FLAC: {p}")
        if info.samplerate != RATE:
            gcd = math.gcd(info.samplerate, RATE)
            mat = resample_poly(mat, RATE // gcd, info.samplerate // gcd, axis=0)
        if mat.shape[1] == 1:
            mat = np.repeat(mat, 2, axis=1)
        # Remove variable leading recording silence while keeping the onset and ~2ms air.
        env = np.max(np.abs(mat), axis=1)
        hit = int(np.argmax(env > max(float(np.max(env)) * .017, 1e-5)))
        return mat[max(0, min(int(.050 * RATE), hit - 96)):, :2].copy()
    finally:
        a.sf_close(handle)


def piano_room(dry, warmth):
    # Small stereo chamber impulse designed here (no additional IR recording/license).
    # The correlated component locates the main source, the differential field supplies width.
    rng = np.random.default_rng(14628)
    n = int(RATE * 1.15)
    t = np.arange(n)/RATE
    diffuse = rng.normal(0, 1, (n, 2)).astype(np.float32)
    diffuse = sosfilt(butter(2, [130, 5300], btype="bandpass", fs=RATE, output="sos"), diffuse, axis=0)
    diffuse *= (np.exp(-t / .19) * np.clip((t-.019)/.044, 0, 1))[:, None]
    for d, l, r in ((.022,.13,.04),(.031,.07,.16),(.049,-.093,.070),(.076,.053,-.049),(.109,.023,.050)):
        diffuse[int(d*RATE)] += [l * 13, r * 13]
    diffuse /= np.linalg.norm(diffuse, axis=0)
    mono = .5 * (dry[:,0] + dry[:,1])
    mixed = dry.copy()
    for c in range(2):
        mixed[:,c] += fftconvolve(mono,diffuse[:,c])[:len(mixed)] * warmth
    # Remove mechanically induced subsonics; preserve the piano's A0 fundamental.
    return sosfilt(butter(2, 24, btype="highpass", fs=RATE, output="sos"), mixed, axis=0).astype(np.float32)


def piano(score, offline):
    end = int((score["duration"] + PIANO_TAIL) * RATE + .5)
    mix = np.zeros((end, 2), dtype=np.float32)
    notes = score["notes"]
    following = {}
    cutoff = {}
    for i in range(len(notes)-1,-1,-1):
        t, d, pitch, v, part = notes[i]
        cutoff[i] = following.get(pitch, float("inf"))
        following[pitch] = t
    pedal = list(score.get("pedal", score.get("pedals", [])))
    down = None
    for t, part, cc, v in sorted(score.get("controls", [])):
        if cc != 64:
            continue
        if v >= 64 and down is None:
            down = t
        if v < 64 and down is not None:
            pedal.append((down,t))
            down = None
    if down is not None:
        pedal.append((down,score["duration"]))
    for i, (t,d,pitch,vel,part) in enumerate(notes):
        onset = max(0, round(t*RATE))
        center = key_center(pitch)
        layer = velocity_layer(vel)
        src = decode_sample(sample_name(pitch, vel), offline)
        ratio = 2 ** ((pitch-center)/12)
        damper = t + d
        # Score author controls pedal changes. No global sustain imposed on Baroque/classical takes.
        for start, end_time in pedal:
            if start <= damper < end_time:
                damper = end_time
                break
        release = .120 + .066 * min(1,d) + (.07 if pitch < 48 else 0)
        # Strings above F6 lack dampers; allow a wider ringing window and natural recorded decay.
        if pitch >= 89:
            release = .42 + (pitch-89)/220
        if cutoff[i] < damper:
            damper = max(t+.018, cutoff[i] - .011)
            release = min(release,.066)
        count = min(end-onset, int((damper-t+release)*RATE), int((len(src)-2)/ratio))
        if count <= 0:
            continue
        if pitch == center:
            wave = src[:count].copy()
        else:
            ix = np.arange(count, dtype=np.float32)*ratio
            j = ix.astype(np.int32)
            frac = (ix-j).astype(np.float32)[:,None]
            wave = src[j] + (src[j+1]-src[j])*frac
        held = min(count,int((damper-t)*RATE))
        tail = count-held
        if tail > 0:
            e = np.linspace(0, 1, tail, dtype=np.float32)
            wave[held:] *= (np.exp(-4.9*e)*np.minimum(1, (1-e)*9))[:,None]
        attack = min(48,count)
        wave[:attack] *= np.linspace(0,1,attack,dtype=np.float32)[:,None]
        last = min(112,count)
        wave[-last:] *= np.linspace(1,0,last,dtype=np.float32)[:,None]
        ref = (LAYER_UPPER[max(layer-2,0)]+LAYER_UPPER[layer-1])*.5
        correction = np.clip((vel/max(12,ref))**.82,.58,1.5)
        # Tighten the close-sampled stereo image slightly, especially in the bass.
        mono = .5*(wave[:,0]+wave[:,1])
        spread = .68 + .16 * np.clip((pitch-34)/44,0,1)
        wave = wave * spread + mono[:,None]*(1-spread)
        mix[onset:onset+count] += wave * correction * .58
    warmth = .14 if score["id"] in {"bach","mozart","rossini"} else .205
    return piano_room(mix, warmth)


@lru_cache(maxsize=1)
def fluidsynth():
    a = lib("fluidsynth")
    p,i,d = C.c_void_p,C.c_int,C.c_double
    signature(a, "new_fluid_settings", p)
    signature(a, "delete_fluid_settings", None,p)
    signature(a, "fluid_settings_setint", i,p,C.c_char_p,i)
    signature(a, "fluid_settings_setnum", i,p,C.c_char_p,d)
    signature(a, "new_fluid_synth",p,p)
    signature(a, "delete_fluid_synth",None,p)
    signature(a, "fluid_synth_sfload",i,p,C.c_char_p,i)
    signature(a, "fluid_synth_program_select",i,p,i,i,i,i)
    signature(a, "fluid_synth_set_interp_method",i,p,i,i)
    signature(a, "fluid_synth_cc",i,p,i,i,i)
    signature(a, "fluid_synth_noteon",i,p,i,i,i)
    signature(a, "fluid_synth_noteoff",i,p,i,i)
    signature(a, "fluid_synth_write_float",i,p,i,p,i,i,p,i,i)
    return a


def pan_value(val):
    # Score data uses absolute MIDI CC 10 by default; normalized bipolar float also accepted.
    if type(val) is float and -1 <= val <= 1:
        return round(63.5+val*63.5)
    return max(0,min(127,int(val)))


def orchestra(score, soundfont):
    a = fluidsynth()
    cfg = a.new_fluid_settings()
    for k, v in {
        "synth.gain": .273, "synth.sample-rate": float(RATE), "synth.reverb.room-size": .47,
        "synth.reverb.damp": .57, "synth.reverb.width": .76, "synth.reverb.level": .41,
    }.items():
        a.fluid_settings_setnum(cfg, k.encode(), v)
    for k,v in {"synth.polyphony": 256, "synth.reverb.active": 1, "synth.chorus.active": 0,
                "synth.midi-channels": 32}.items():
        a.fluid_settings_setint(cfg,k.encode(),v)
    synth = a.new_fluid_synth(cfg)
    if not synth:
        a.delete_fluid_settings(cfg)
        raise RuntimeError("Could not initialize FluidSynth")
    try:
        sfid = a.fluid_synth_sfload(synth, str(soundfont).encode(), 1)
        if sfid < 0:
            raise RuntimeError(f"Could not load {soundfont}")
        a.fluid_synth_set_interp_method(synth, -1, 7)
        map_parts = []
        next_chan = iter(c for c in range(32) if c != 9)
        for part in score["parts"]:
            program = part["program"]
            percussion = program in (-1,128) or part.get("percussion", False)
            chan = 9 if percussion else next(next_chan)
            map_parts.append(chan)
            bank = 128 if percussion else 0
            if a.fluid_synth_program_select(synth,chan,sfid,bank,0 if percussion else program) != 0:
                raise RuntimeError(f"No GM preset {part} in {soundfont}")
            volume = part.get("volume", 100)
            a.fluid_synth_cc(synth,chan,7,round(volume))
            a.fluid_synth_cc(synth,chan,10,pan_value(part.get("pan",64)))
            a.fluid_synth_cc(synth,chan,91,47 if percussion else 39)
            a.fluid_synth_cc(synth,chan,93,0)
        notes = score["notes"]
        events = []
        following = {}
        for sequence in range(len(notes)-1,-1,-1):
            onset, duration, pitch, vel, part = notes[sequence]
            channel = map_parts[part]
            on = max(0,round(onset*RATE))
            pair = (channel, pitch)
            off = max(on+1,round((onset+duration)*RATE))
            off = min(off, following.get(pair,off))
            if off <= on:
                continue
            following[pair] = on
            events.append((on,2,channel,pitch,vel))
            events.append((off,0,channel,pitch,0))
        for onset, part, control, value in score.get("controls",score.get("cc",[])):
            events.append((round(onset*RATE),1,map_parts[part],control,value))
        n = round((score["duration"]+ORCH_TAIL)*RATE)
        stereo = np.zeros((n,2),dtype=np.float32)
        ptr = stereo.ctypes.data
        cursor = 0
        for frame,type_,ch,note,val in sorted(events):
            frame = min(n, max(0, int(frame)))
            if frame > cursor:
                if a.fluid_synth_write_float(synth,frame-cursor,ptr,2*cursor,2,ptr,2*cursor+1,2) != 0:
                    raise RuntimeError("FluidSynth frame rendering failed")
                cursor = frame
            if type_ == 2:
                a.fluid_synth_noteon(synth,ch,note,val)
            elif type_ == 0:
                a.fluid_synth_noteoff(synth,ch,note)
            else:
                a.fluid_synth_cc(synth,ch,note,val)
        a.fluid_synth_write_float(synth,n-cursor,ptr,2*cursor,2,ptr,2*cursor+1,2)
        return sosfilt(butter(2,23,btype="highpass",fs=RATE,output="sos"),stereo,axis=0).astype(np.float32)
    finally:
        a.delete_fluid_synth(synth)
        a.delete_fluid_settings(cfg)


def ffmpeg(*args, data=None, check=True):
    return subprocess.run(["ffmpeg","-nostdin","-hide_banner",*map(str,args)],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check)


def stats(media, data=None):
    p = ffmpeg(*media,"-af","ebur128=peak=true","-f","null","-",data=data)
    log = p.stderr.decode(errors="replace").rsplit("Summary:",1)[-1]
    def grab(pat): return float(re.search(pat,log).group(1))
    return {"integrated_lufs":grab(r"I:\s*(-?[\d.]+) LUFS"),
            "range_lu":grab(r"LRA:\s*(-?[\d.]+) LU"),
            "true_peak_dbtp":grab(r"Peak:\s*(-?[\d.]+) dBFS")}


RAW = ["-f","f32le","-ar",RATE,"-ac","2","-i","pipe:0"]


def master(score, raw, output, lossless):
    n = len(raw)
    if not np.isfinite(raw).all() or np.max(np.abs(raw)) < 1e-5:
        raise ValueError(f"Silence or invalid PCM: {output.name}")
    fade = round(.25*RATE)
    raw[-fade:] *= np.linspace(1,0,fade,dtype=np.float32)[:,None]
    pcm = raw.astype("<f4",copy=False).tobytes()
    initial = stats(RAW,pcm)
    dest_lufs = -17.5 if score["mode"]=="piano" else -17
    # Linked, constant stereo gain only: no phrase-level compression or limiting.
    gain = min(dest_lufs-initial["integrated_lufs"], -1.8-initial["true_peak_dbtp"])
    temp = output.with_name(output.stem+".partial.mp3")
    try:
        ffmpeg("-loglevel","error","-y",*RAW,"-af",f"volume={gain:.4f}dB","-map_metadata","-1",
               "-c:a","libmp3lame","-q:a","2","-id3v2_version","3",
               "-metadata",f"title={score['id'].title()} | {score['mode'].title()}",
               "-metadata","album=Another Can-Can",temp,data=pcm)
        metadata = stats(["-i",temp])
        if metadata["true_peak_dbtp"] > -1.0:
            raise ValueError(f"Encoded headroom narrower than -1 dBTP: {temp}")
        if lossless:
            ffmpeg("-loglevel","error","-y",*RAW,"-af",f"volume={gain:.4f}dB",
                   "-c:a","flac","-sample_fmt","s32","-bits_per_raw_sample","24",
                   CACHE/"masters"/f"{output.stem}.flac",data=pcm)
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    pcm_check = np.frombuffer(ffmpeg("-loglevel","error","-i",output,"-f","f32le","-").stdout,dtype="<f4").reshape(-1,2)
    exc = np.flatnonzero(np.max(np.abs(pcm_check),axis=1)>10 ** (-45/20))
    if not len(exc):
        raise ValueError(f"Audio unexpectedly near silent: {output}")
    meta = subprocess.check_output(["ffprobe","-v","error","-show_entries","stream=codec_name,sample_rate,channels,duration",
                                   "-of","json",str(output)],text=True)
    stream = json.loads(meta)["streams"][0]
    return {"file":str(output.relative_to(ROOT)), "sha256":sha(output), **stream,
            "score_seconds":score["duration"],"frames":n,"decoded_frames":len(pcm_check),
            "first_audible_s":round(float(exc[0])/RATE,4),"last_audible_s":round(float(exc[-1])/RATE,4),
            "gain_db":round(gain,3),"rms_dbfs":[round(float(20*np.log10(np.sqrt(np.mean(pcm_check[:,i]**2)))),2) for i in range(2)],
            **metadata}


def cli():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("selection",nargs="*",help="basename(s) of exact score variants (all by default)")
    ap.add_argument("--offline",action="store_true",help="require instrument assets already in .cache")
    ap.add_argument("--lossless",action="store_true",help="retain 24-bit FLAC in .cache/masters")
    ap.add_argument("--prefetch",action="store_true",help="download required assets but do not render")
    ap.add_argument("--soundfont",type=Path,help="advanced: override GS SoundFont for orchestra")
    ap.add_argument("--jobs",type=int,default=3)
    ap.add_argument("--score-dir",type=Path,default=ROOT/"music"/"performances")
    ns = ap.parse_args()
    files = sorted(ns.score_dir.glob("*.json")) if not ns.selection else [ns.score_dir/f"{x}.json" for x in ns.selection]
    if not files:
        ap.error(f"no score files in {ns.score_dir}")
    selections = {p.stem:json.loads(p.read_text()) for p in files}
    for name,s in selections.items():
        if name != s["id"]+"-"+s["mode"] or not s["notes"] or s["mode"] not in ("piano","orchestra"):
            raise ValueError(f"Invalid score: {name}")
    sf = None
    if any(s["mode"]=="orchestra" for s in selections.values()):
        sf = ns.soundfont or fetch(GS,"GeneralUser-GS.sf2",CACHE/"GeneralUser-GS.sf2",offline=ns.offline,digest=GS_HASH)
    names = sorted({sample_name(n,v) for s in selections.values() if s["mode"]=="piano" for _,_,n,v,_ in s["notes"]})
    acquire(names,ns.offline)
    if ns.prefetch:
        print(f"Ready: {len(names)} piano samples and orchestra SoundFont {sf}")
        return
    outdir = ROOT/"site"/"audio"
    outdir.mkdir(parents=True,exist_ok=True)
    (CACHE/"masters").mkdir(parents=True,exist_ok=True)
    score_paths = {p.stem: p for p in files}
    def job(item):
        name,s = item
        raw = piano(s,True) if s["mode"]=="piano" else orchestra(s,sf)
        report = master(s,raw,outdir/f"{name}.mp3",ns.lossless)
        report["score_sha256"] = sha(score_paths[name])
        print(f"{name:24s} {float(report['duration']):6.2f}s / {report['integrated_lufs']:5.1f} LUFS / {report['true_peak_dbtp']:5.1f} dBTP",flush=True)
        return name,report
    qa = ROOT/"qa"/"audio-report.json"
    old = json.loads(qa.read_text()) if qa.exists() else {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=ns.jobs) as pool:
        records = dict(pool.map(job,selections.items()))
    if len({r["sha256"] for r in records.values()})!=len(records):
        raise ValueError("Duplicate audio takes")
    result = {"sample_rate":RATE, "tracks":{**old.get("tracks",{}),**records},
              "soundfont_sha256":sha(sf) if sf else old.get("soundfont_sha256"),
              "soundfont_commit":"684543d5e5efaef08d02be50dcda8d552478fa60",
              "piano_commit":"3382bf9496bba2486f5ab0de55a264d1dfc38404",
              "piano_samples":{**old.get("piano_samples",{}),**{p:sha(CACHE/"piano"/p) for p in names}}}
    qa.parent.mkdir(parents=True,exist_ok=True)
    temporary = qa.with_suffix(".tmp")
    temporary.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    temporary.replace(qa)


if __name__=="__main__":
    cli()
