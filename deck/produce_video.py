"""Assemble the finished, narrated demo video end-to-end.

Prereq: the 8 narration clips + durations.json already exist in deck/video/audio/
(made by the edge-tts step, voice en-US-GuyNeural), and the KEYED app is serving
on :8000 with a warm cache (bat run + fair compare).

Pipeline:
  1. size each beat's on-screen hold to its TTS segment length -> holds.json
  2. re-record the picture (capture_video.py) timed to the narration -> walkthrough.webm + cues.json
  3. mux: drop each S*.mp3 at its real beat offset, overlay onto the video -> walkthrough_narrated.mp4

Fully hands-off: the result is a finished, narrated mp4 (one continuous ride,
no time-jump cut — the warm cache streams the run in immediately). Run:
    .venv/Scripts/python.exe deck/produce_video.py
"""
from __future__ import annotations
import json
import os
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
HERE = Path(__file__).resolve().parent
V = HERE / "video"
A = V / "audio"
PYEXE = os.environ.get("PYEXE", str(HERE.parent / ".venv" / "Scripts" / "python.exe"))
SEGS = [f"S{i}" for i in range(1, 9)]


def dur(path: Path) -> float:
    out = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    h, mn, s = m.groups()
    return int(h) * 3600 + int(mn) * 60 + float(s)


def main():
    d = json.loads((A / "durations.json").read_text())

    # 1) per-beat holds sized to the narration. Action-heavy beats subtract a
    #    conservative minimum action time (which always adds slack on top).
    holds = {
        "hook": d["S1"], "number": d["S2"], "setup": max(4.0, d["S3"] - 1.0),
        # Run clicked -> S4 immediately: the warm cache streams the whole
        # conversation in right away, so the ride is continuous (no cut).
        "collab": round(d["S4"] + 1.0, 2),
        "diagram": round(d["S5"] * 0.30, 2), "review": round(d["S5"] * 0.30, 2),
        "pcb": round(d["S5"] * 0.40, 2),
        "output": max(8.0, d["S6"] - 5.0), "compare": max(8.0, d["S7"] - 4.0),
        "close": d["S8"] + 1.0,
    }
    (A / "holds.json").write_text(json.dumps(holds, indent=2))
    print(">> holds sized to narration:", {k: round(v, 1) for k, v in holds.items()})

    # 2) re-record the picture, timed to the narration. VIDEO_SKIP_RECORD=1
    #    reuses the existing walkthrough.webm + cues.json (e.g. to re-run only
    #    the mux after an audio/card tweak).
    webm = V / "walkthrough.webm"
    if os.environ.get("VIDEO_SKIP_RECORD") == "1" and webm.exists() and (V / "cues.json").exists():
        print(">> VIDEO_SKIP_RECORD=1 - reusing existing walkthrough.webm + cues.json")
    else:
        env = dict(os.environ, VIDEO_HOLDS_JSON=str(A / "holds.json"),
                   GALLERY_URL=os.environ.get("GALLERY_URL", "http://localhost:8000"))
        print(">> recording picture (this replays the cached run; a few minutes)…")
        if subprocess.run([PYEXE, str(HERE / "capture_video.py")], env=env).returncode != 0:
            raise SystemExit("capture_video failed")
    cues = json.loads((V / "cues.json").read_text())
    offset = {c["segment"]: c["t"] for c in cues if c["segment"].startswith("S")}
    missing = [s for s in SEGS if s not in offset]
    if missing:
        raise SystemExit(f"no beat offset for {missing} — check the recording")

    # 3) mux narration: each clip delayed to its beat offset, mixed over the
    #    video. No cut card anymore — with the warm cache the run streams in
    #    immediately, so a "minutes later" jump would be dishonest and jarring.
    inputs = []
    for s in SEGS:
        inputs += ["-i", str(A / f"{s}.mp3")]
    filt = []
    for idx, s in enumerate(SEGS, start=1):  # input 0 = video, 1..8 = audio
        off = int(offset[s] * 1000)
        filt.append(f"[{idx}:a]adelay={off}:all=1,aformat=channel_layouts=stereo[a{idx}]")
    filt.append("".join(f"[a{i}]" for i in range(1, len(SEGS) + 1))
                + f"amix=inputs={len(SEGS)}:normalize=0[aout]")

    mp4 = V / "walkthrough_narrated.mp4"
    cmd = [FF, "-y", "-i", str(webm), *inputs, "-filter_complex", ";".join(filt),
           "-map", "0:v", "-map", "[aout]",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(mp4)]
    print(">> muxing narration -> mp4…")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit("ffmpeg mux failed")

    # 4) keep the final under the Devpost 3:00 cap: uniformly speed-fit if needed
    #    (atempo preserves pitch; imperceptible on a screencast + calm narration)
    total = dur(mp4)
    TARGET = 176.0
    final = V / "walkthrough_final.mp4"
    factor = 1.0
    if total > TARGET:
        factor = round(total / TARGET, 4)
        print(f">> speed-fit x{factor} to land under 3:00…")
        r = subprocess.run(
            [FF, "-y", "-i", str(mp4),
             "-filter_complex", f"[0:v]setpts=PTS/{factor}[v];[0:a]atempo={factor}[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", str(final)], capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[-2000:])
            raise SystemExit("speed-fit failed")
    else:
        import shutil
        shutil.copyfile(mp4, final)

    ftotal = dur(final)
    print(f"\n  ok {final.name}  {int(ftotal // 60)}:{int(ftotal % 60):02d}  "
          f"({final.stat().st_size // 1024} KB)  [speed x{factor}]")


if __name__ == "__main__":
    main()
