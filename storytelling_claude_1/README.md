# storytelling_claude_1

Do vague cold prompts like *"tell me a story please"* make chat models collapse
into the same story? The pilot data says yes: an old **lighthouse keeper**, a
**great lamp**, **forty years**, **spiral stairs**, a **storm**, a rescued
**boat**, a gentle moral, and a *"Want another?"* sign-off — the same skeleton
again and again, even across Claude and GPT.

This is a deliberately small harness to measure how often that attractor shows
up across prompts, providers, and two interventions (a randomization prompt and
a suppression prompt).

## What's here

Three files do everything:

- `config.yaml` — models, prompts, and run settings. The only file you edit.
- `run.py` — calls the APIs and appends each story to one flat CSV. Resumable.
- `analyze.py` — scores the lighthouse attractor and summarizes by cell.

Storage is a single CSV (`data/stories.csv`). No database, no exports, no
shards. If a run is interrupted, every finished story is already saved and you
just run the same command again to continue.

## Design

- **8 prompts × 3 providers × `n_per_cell`.** At `n=100` that's 2,400 stories.
- Calls are ordered *by replicate* (replicate 1 across all cells, then 2, …),
  so a partial run is still balanced across every condition.
- The analyzer is **unsupervised**: instead of checking for a known motif it
  clusters each prompt cell's stories by semantic similarity (sentence
  embeddings) and surfaces whatever attractors exist, reporting three "same
  story" signals for each — semantic meaning, verbatim phrasing, and shared
  setting. The lighthouse is kept as one named baseline flag on top — see below.

## Setup

```bash
cd storytelling_claude_1
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your API keys
```

Open `config.yaml` and **confirm the model strings**. As of writing,
`claude-sonnet-4-6` is a real, current Anthropic model. The OpenAI and Gemini
strings are placeholders matching the study's "average free-user" intent —
verify them against each provider's current model list, since a wrong model ID
is the most likely thing to break a run.

## Run

```bash
# Smoke test first — 12 calls, check the CSV looks right:
python run.py --limit 12

# One provider at a time (handy if quotas differ):
python run.py --provider anthropic

# The full study (resumable — just rerun if interrupted):
python run.py

# Re-attempt any rows that errored (bad model ID, quota, etc.):
python run.py --retry-errors
```

## Analyze — discover attractors

```bash
python analyze.py
```

The lighthouse parable was a *surprise*, so the analyzer doesn't just check for
it — it **discovers** attractors. Within each prompt cell it clusters the stories
by similarity and flags any cluster that's tight and large enough as an
attractor. Whatever the next lighthouse turns out to be, it shows up on its own.

For each cluster it reports **three "same story" signals**, because sameness can
mean three different things:

- `sem` — **semantic** meaning similarity (sentence embeddings). Catches the same
  story told in totally different words — e.g. a lighthouse keeper and a desert
  well-tender who keep a guiding light alive for travelers who never come are the
  *same parable* despite sharing almost no vocabulary.
- `phr` — **phrase** overlap (verbatim 2–3 grams). Catches reused wording like
  "rocky spit of land".
- `set` — **setting** overlap (shared who/where/object words). Names the trope
  ("keeper + lighthouse + sea" vs "clockmaker + town + shop").

Clustering uses the semantic signal by default — it's the most robust and the
one that catches structural twins. The other two are reported alongside so you
can see *which kind* of sameness drove each cluster.

The known lighthouse cluster is also kept as a single named `is_lighthouse`
baseline flag, so you can track it across runs without re-deriving it.

Semantic clustering uses `sentence-transformers` (default model
`all-MiniLM-L6-v2` — small, ~80MB, downloaded once on first run, and close
enough to the heavier models for grouping stories). **If it isn't installed, the
analyzer automatically falls back to TF-IDF and tells you** — so it always runs,
just with a weaker `sem` signal. For best results, install it (it's in
requirements.txt); for maximum quality on subtle distinctions, pass
`--model all-mpnet-base-v2` (~420MB).

Outputs:

- `data/attractors.csv` — one row per discovered cluster (size, share, the three
  signals, lighthouse share, fingerprint phrases, setting words).
- `data/scored.csv` — one row per story (its cluster id + the lighthouse flag).

Useful knobs:

```bash
python analyze.py --prompt P05_strange_variant     # one cell
python analyze.py --tightness 0.45                 # coarser clusters (merge more)
python analyze.py --min-cluster 5                  # only larger collapses count
python analyze.py --model all-mpnet-base-v2         # heavier, max-quality
python analyze.py --tfidf                          # skip embeddings entirely
```

`--tightness` is a distance cut: lower = stricter (stories must be more alike to
group). The default is 0.35 for embeddings, 0.55 for TF-IDF. If one real trope
splits into near-duplicates, raise it; if unrelated stories get lumped, lower it.

## Prompt cells

| id | prompt |
|---|---|
| P01_baseline_please | tell me a story please |
| P02_baseline_plain | tell me a story |
| P03_write_variant | write me a story |
| P04_short_variant | tell me a short story please |
| P05_strange_variant | tell me a strange story please |
| P06_funny_variant | tell me a funny story please |
| P07_random_setting | tell me a story please. First choose a random setting and genre. |
| P08_suppression | tell me a story please, but not about lighthouses, lamps, the sea, ships, storms, fog, islands, cliffs, or old caretakers. |

Edit prompt text in `config.yaml`. The text *is* the experimental condition, so
change it deliberately.

## What changed from storytelling_1

The previous version was over-built for a 2,400-row study and, more importantly,
didn't run (`run.py` imported a `provider_factory` module that didn't exist).
This rewrite keeps the good ideas — balanced ordering, resumability, the motif
families — and drops what wasn't earning its keep: SQLite + WAL, gzip/sharded
JSONL exports, a JSON schema, a provider class hierarchy + factory, and separate
`score`/`summarize`/`export` subcommands. And since the lighthouse parable was
a surprise, the analyzer was rebuilt to *discover* attractors by clustering
rather than scoring for the one motif we happened to notice — so the next
surprise shows up on its own.
