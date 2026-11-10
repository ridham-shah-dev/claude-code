#!/usr/bin/env python3
"""Make narration for each line with edge-tts and mix it onto a silent track at the right times.
usage: make_voice.py episode.json [voice]   (default voice en-US-GuyNeural)
Needs: pip install edge-tts   and ffmpeg."""
import asyncio, json, os, subprocess, sys

import edge_tts


async def main(path, voice):
    d = json.load(open(path, encoding="utf-8"))
    out = os.path.dirname(os.path.abspath(path))
    vdir = os.path.join(out, "voice")
    os.makedirs(vdir, exist_ok=True)
    texts = [(l["t"], l["voice"]) for l in d["lines"]]
    v = d["vote"]
    texts.append((v["t"], v["spoken"]))
    inputs, filters = [], []
    for i, (t, text) in enumerate(texts):
        f = os.path.join(vdir, f"l{i:02d}.mp3")
        await edge_tts.Communicate(text, voice, rate="+0%").save(f)
        inputs += ["-i", f]
        ms = int(t * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(texts)))
    filters.append(f"{mix}amix=inputs={len(texts)}:normalize=0[out]")
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters),
           "-map", "[out]", "-t", str(d["end"]), os.path.join(out, "voice.mp3")]
    subprocess.run(cmd, check=True)
    print("wrote", os.path.join(out, "voice.mp3"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: make_voice.py episode.json [voice]")
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "en-US-GuyNeural"))
