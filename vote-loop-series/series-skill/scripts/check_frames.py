#!/usr/bin/env python3
"""Find black, frozen or glitched frames, and report mean brightness.
usage: check_frames.py series/ep01/frames [--allow-frozen N]
Needs: pip install pillow numpy"""
import os, sys

import numpy as np
from PIL import Image


def main(folder, allow_frozen=4):
    files = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
    if not files:
        sys.exit("no frames")
    prev, frozen_run, problems, means = None, 0, [], []
    for i, f in enumerate(files):
        g = np.asarray(Image.open(os.path.join(folder, f)).convert("L"), dtype=np.float32)
        m = float(g.mean())
        means.append(m)
        if m < 3:
            problems.append((i, "black frame"))
        if prev is not None:
            diff = float(np.abs(g - prev).mean())
            if diff < 0.05:
                frozen_run += 1
                if frozen_run == allow_frozen:
                    problems.append((i, f"frozen for {allow_frozen}+ frames"))
            else:
                frozen_run = 0
            if diff > 60:
                problems.append((i, f"sudden jump (diff {diff:.0f}), possible glitch or snap"))
        # black wedge: a large fully black block inside a non-dark frame
        if m > 25:
            h, w = g.shape
            for y in range(0, h, h // 8):
                for x in range(0, w, w // 6):
                    blk = g[y:y + h // 8, x:x + w // 6]
                    if blk.size and blk.max() < 2:
                        problems.append((i, f"black block at x={x} y={y}"))
                        break
        prev = g
    avg = sum(means) / len(means)
    print(f"{len(files)} frames, mean brightness {avg:.0f}/255 (target about 50)")
    for i, msg in problems:
        print(f"frame {i} (t={i/30:.2f}s): {msg}")
    print("CLEAN" if not problems else f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: check_frames.py frames_folder")
    main(sys.argv[1])
