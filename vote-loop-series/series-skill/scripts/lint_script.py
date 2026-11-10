#!/usr/bin/env python3
"""Lint an episode.json against the Vote Loop rules. Exit 1 on any failure."""
import json, re, sys

BANNED = ["comment 1 to unlock", "share or it dies", "pikachu", "pokemon", "pokémon",
          "mickey", "naruto", "goku", "spider-man", "spiderman", "mario", "zelda"]
PASSIVE = ["nothing", "wait", "stay", "do nothing", "ignore", "sit"]
SAFE_X = (120, 960)
fails, warns = [], []


def fail(m): fails.append(m)
def warn(m): warns.append(m)


def main(path):
    d = json.load(open(path, encoding="utf-8"))
    lines = sorted(d.get("lines", []), key=lambda l: l["t"])
    if not lines:
        fail("no lines"); return
    first = lines[0]
    if first["t"] != 0.0:
        fail("first line must start at t=0.0 (frame one is mid-action)")
    if len(first["voice"].split()) > 7:
        fail(f"first line is {len(first['voice'].split())} words, max 7")
    if not first.get("red"):
        fail("first line needs one red stake word ('red')")
    low = first["voice"].lower()
    if not re.search(r"\byou(r|'re|'ll)?\b", low):
        fail("first line must be second person ('you')")

    # stamp credit by second 4 (not on episode 1)
    if d.get("previous_vote_winner"):
        st = d.get("stamp")
        if not st or st["t"] > 4.0:
            fail("last vote must be credited by second 4 with a stamp")
    # wide shot by 6 s
    if d.get("wide_shot_t") is None or d["wide_shot_t"] > 6.0:
        fail("one wide shot by second 6 (set wide_shot_t <= 6.0)")

    # pacing: something happens ~every 3 s
    gaps = [b["t"] - a["t"] for a, b in zip(lines, lines[1:])]
    if gaps and max(gaps) > 6.0:
        fail(f"gap of {max(gaps):.1f}s between lines; something must happen about every 3 s")
    if gaps and sum(gaps) / len(gaps) > 4.5:
        warn(f"average gap {sum(gaps)/len(gaps):.1f}s, target about 3 s")
    for l in lines:
        if not l.get("event") and not l.get("shot"):
            warn(f"line at {l['t']}s has no shot/event")

    # words per sentence
    sents = []
    for l in lines:
        sents += [s for s in re.split(r"[.!?]+", l["voice"]) if s.strip()]
    avg = sum(len(s.split()) for s in sents) / max(1, len(sents))
    if avg > 5.5:
        fail(f"average {avg:.1f} words per sentence, target about 4")
    explain = [l for l in lines if len(l["voice"].split()) > 12]
    if explain:
        fail("lines over 12 words: " + "; ".join(l["voice"][:30] for l in explain))

    # speaking speed 2.6 words/s
    for a, b in zip(lines, lines[1:]):
        need = len(a["voice"].split()) / 2.6
        if need > (b["t"] - a["t"]) + 0.4:
            fail(f"line at {a['t']}s needs {need:.1f}s to speak but only has {b['t']-a['t']:.1f}s")

    # captions
    for l in lines:
        cap = l.get("caption", "")
        if cap and len(cap.split()) > 4:
            fail(f"caption '{cap}' has more than 4 words")

    # spectacle at 60-65 %
    end = d.get("end")
    sp = d.get("spectacle")
    if not end:
        fail("missing 'end'")
    elif not sp:
        fail("missing spectacle")
    else:
        r = sp["t"] / end
        if not 0.55 <= r <= 0.70:
            fail(f"spectacle at {r*100:.0f}% of runtime, target 60-65%")
        if not 3.0 <= sp.get("duration", 0) <= 4.5:
            warn("spectacle should be 3-4 s")
    if not d.get("ticking_number"):
        fail("needs a ticking number")
    if not d.get("clue"):
        fail("needs one hidden clue")

    # vote
    v = d.get("vote")
    if not v:
        fail("missing vote"); return
    opts = v.get("options", [])
    if not 2 <= len(opts) <= 3:
        fail(f"{len(opts)} vote options, must be 2 or 3")
    for o in opts:
        if any(p in o["verb"].lower() for p in PASSIVE):
            fail(f"option '{o['verb']}' looks passive; nobody votes to do nothing")
        if not o.get("next_opens") or o["next_opens"].strip() in ("", "..."):
            fail(f"option {o['n']} has no 'next_opens'; the vote isn't real yet")
        if o.get("pulls_on") not in ("curiosity", "protection", "escape", "revenge"):
            fail(f"option {o['n']} pulls_on must be curiosity/protection/escape/revenge")
    pulls = [o.get("pulls_on") for o in opts]
    if len(set(pulls)) < len(pulls):
        warn("two options pull on the same instinct")
    if end and v["t"] and end - v["t"] > 7.0:
        fail(f"vote + end card is {end - v['t']:.1f}s, must be under 7 s")
    if not v.get("spoken") or not v.get("caption"):
        fail("say the vote three ways: spoken, caption, pills")
    if end and lines[-1]["t"] > v["t"]:
        warn("narration line after vote start")

    # banned / bait
    blob = json.dumps(d, ensure_ascii=False).lower()
    for b in BANNED:
        if b in blob:
            fail(f"banned or bait wording: '{b}'")
    if re.search(r"\b1\s*=|comment\s+\d", d.get("caption_text", "").lower()):
        fail("vote number in the caption")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: lint_script.py episode.json")
    main(sys.argv[1])
    for w in warns: print("WARN:", w)
    for f in fails: print("FAIL:", f)
    print("OK" if not fails else f"{len(fails)} failure(s)")
    sys.exit(1 if fails else 0)
