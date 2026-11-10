#!/usr/bin/env python3
"""Render series/epNN/episode.html to frames, then to final.mp4 with voice.mp3.
usage: render.py series/ep01 [fps=30]
The page must define window.EP_DURATION (seconds) and window.drawFrame(t) that draws
deterministically on <canvas id="c"> (1080x1920).
Needs: pip install playwright && playwright install chromium ; ffmpeg."""
import base64, json, os, subprocess, sys

from playwright.sync_api import sync_playwright


def main(folder, fps=30):
    folder = os.path.abspath(folder)
    html = os.path.join(folder, "episode.html")
    frames = os.path.join(folder, "frames")
    os.makedirs(frames, exist_ok=True)
    for f in os.listdir(frames):
        os.remove(os.path.join(frames, f))
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1080, "height": 1920})
        page.goto("file://" + html)
        page.wait_for_function("window.drawFrame && window.EP_DURATION")
        dur = page.evaluate("window.EP_DURATION")
        n = int(dur * fps)
        for i in range(n):
            page.evaluate(f"window.drawFrame({i / fps})")
            data = page.evaluate("document.getElementById('c').toDataURL('image/png')")
            with open(os.path.join(frames, f"f{i:05d}.png"), "wb") as fh:
                fh.write(base64.b64decode(data.split(",", 1)[1]))
        b.close()
    print(f"{n} frames")
    voice = os.path.join(folder, "voice.mp3")
    cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", os.path.join(frames, "f%05d.png")]
    if os.path.exists(voice):
        cmd += ["-i", voice, "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            os.path.join(folder, "final.mp4")]
    subprocess.run(cmd, check=True)
    print("wrote", os.path.join(folder, "final.mp4"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: render.py series/ep01 [fps]")
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 30)
