# tell-me-a-story

What does a chat model do when you give it the vaguest possible prompt —
*"tell me a story please"* — with no other guidance? Does it reach for
something fresh each time, or does it fall into the same groove over and over?

This repo investigates that question across multiple LLM providers. The short
answer so far: **the groove is real.** In early testing, vague story prompts
collapsed with surprising regularity into a single shape — an old **lighthouse
keeper** who has tended a **great lamp** for **forty years**, climbs the
**spiral stairs** on a **stormy night**, and guides a lost **boat** safely home,
ending with a gentle moral and *"Want another?"* The same skeleton recurred
across separate generations, sometimes nearly word for word ("a rocky spit of
land where the sea never quite stopped arguing with the shore").

The goal of the study is to measure how strong that pull is, whether it differs
by provider, and what kinds of prompts break it — and, importantly, to discover
*other* attractors we didn't already know to look for.

## What's here

```
tell-me-a-story/
├── storytelling_claude_1/        ← the current study (run this)
│   ├── run.py                    generate stories → flat CSV, resumable
│   ├── analyze.py                discover attractors, three similarity signals
│   ├── config.yaml               models, prompts, run settings (the one file you edit)
│   ├── requirements.txt
│   ├── .env.example              copy to .env and add your API keys
│   ├── README.md                 full study docs — start here
│   ├── data/                     run output (stories.csv); not committed
│   └── data_sample/              a tiny sample CSV showing the data shape
├── original_overcooked_plan/     the original first-pass harness (superseded; provenance, not maintained)
├── story_test_pilot_Opus47_GPT.txt  the hand-collected pilot that started this
├── LICENSE
└── README.md                     (this file)
```

The active study is **`storytelling_claude_1/`** — its README has the full
setup, run, and analysis instructions.

## The study in one paragraph

Eight prompt variants (plain baselines, mood variants like "funny" / "strange",
and two interventions — one asking the model to randomize setting and genre,
one explicitly forbidding the lighthouse furniture) are sent to each provider
`n` times. Every generation is written immediately to a flat CSV, so a run is
resumable and an interrupted run is still usable. The analyzer then clusters the
stories within each prompt cell by semantic similarity and surfaces whatever
attractors exist — reporting, for each, three "same story" signals (semantic
meaning, verbatim phrasing, and shared setting) plus the phrases and tropes that
define it. The known lighthouse pattern is kept as a named baseline flag.

## Status

Active. Current runs cover OpenAI and Anthropic at `n=100` per prompt; Gemini is
temporarily disabled (its free-tier daily quota is far below what the study
needs — see the study README). Results are regenerable and are not committed to
the repo; a small sample lives in `storytelling_claude_1/data_sample/stories_sample.csv`.

## A note on the older harness

`original_overcooked_plan/` is the original harness — a more elaborate design
(SQLite, sharded exports, a provider class hierarchy) that was rebuilt into the
simpler, working version now in `storytelling_claude_1/`. It's kept for
provenance and is not maintained (it doesn't run as-is — see the study README).
`story_test_pilot_Opus47_GPT.txt` is the original hand-collected set of
generations that first revealed the lighthouse pattern.
