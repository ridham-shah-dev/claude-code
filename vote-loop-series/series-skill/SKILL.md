---
name: vote-loop-series
description: Make a vertical short-video story series where viewers vote on what happens next. Use when the user wants a new episode, a series bible, a vote, a pinned comment, covers, or a script for a vote-loop series. Every frame is drawn in code (HTML canvas) and rendered with ffmpeg. Original characters only.
---

# Vote Loop Series

You turn one idea into a finished vertical episode (1080x1920, 30 fps) that ends on a vote,
and you prepare the next episode from the results.

Read `references/rules.md` before writing anything. It holds the rules this skill follows.

## Hard rules
- Original characters and worlds only. Never use Pokemon, Disney, anime or any other known character, art, music or logos. If the user's idea uses one, say so and propose an original replacement with the same feel.
- No AI video. Every frame comes from `episode.html` drawn with code.
- Never post or share the series bible. It holds every answer.
- No gore. Dread comes from numbers and silence.

## Workflow (stop three times for the user's OK)

### Step 0: setup (first run only)
1. Ask for one idea in one line, plus the series name and the "you" role.
2. Copy `templates/bible.md` to `series/bible.md` and fill it: world laws (max 4), cast, a companion who makes choices, mysteries and the episode where each one pays off, clues with payoff episodes.
3. **STOP 1:** show the bible summary, get OK.

### Step 1: script
1. Copy `templates/episode.json` to `series/ep01/episode.json`. Fill it using the rules (first line 7 words or fewer, 2nd person, present tense, about 4 words per sentence, something happens every ~3 s, a ticking number, one spectacle at 60-65%, one hidden clue, vote under 7 s).
2. Fill the vote worksheet in `templates/vote-worksheet.md`. Write how the next episode opens for EVERY option. If you can't, the vote isn't real.
3. Run `python3 scripts/lint_script.py series/ep01/episode.json` and fix every failure.
4. **STOP 2:** show the script as a second-by-second table and the vote. Get OK.

### Step 2: draw and render
1. Build `series/ep01/episode.html` from `templates/episode.html`. Rules: dark, glowing, moving; four or five "home" setups; every shot moves; text only inside the safe frame; one text layer at a time.
2. Make narration: `python3 scripts/make_voice.py series/ep01/episode.json` (uses edge-tts; ~2.6 words a second).
3. Render: `python3 scripts/render.py series/ep01` (needs playwright + ffmpeg).
4. Run `python3 scripts/check_frames.py series/ep01/frames` to find black, frozen or glitched frames. Fix and re-render until clean.
5. **STOP 3:** deliver `series/ep01/final.mp4` and ask the user to watch it fully at full size before posting.

### Step 3: posting pack
Write `series/ep01/posting.md` from `templates/posting.md`: title, caption (asks the question in words, no vote on cover or first line), vote pin, clue pin, newcomer pin, three cover options, countdown plan, Story week plan. No spoilers anywhere.

### Next episode
When the user brings vote results: record them in `series/results.md`, open the next script with "MOST OF YOU SAID -> [winner]" by second 4, and keep the one rule: the vote must visibly change the next part.

## Never
- Bait wording ("Comment 1 to unlock", "Share or it dies").
- Four options or a do-nothing option.
- Opening on the past or reading results over a frozen frame.
- Confirming a theory or hinting at the next part.
- Changing the story after the picture is locked.
