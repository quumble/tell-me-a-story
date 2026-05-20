# storytelling_1

A small, resumable API harness for testing whether vague story prompts collapse into recurring motifs such as lighthouse keepers, lamps, storms, and moral parables.

This folder is configured for the **average free-user interface behavior** study design:

- 8 prompt cells
- 3 model/provider cells
- `n=100` per model × prompt cell
- 2,400 planned story generations total

The code writes every completed generation immediately to SQLite, so an interrupted run is still usable.

## Model set

The default API proxy models are in `study_config.yaml`:

| Provider | Default model |
|---|---|
| OpenAI | `gpt-5.5` |
| Anthropic | `claude-sonnet-4-6` |
| Google Gemini | `gemini-3.5-flash` |

Notes:

- ChatGPT's exact free-user routing, including any "Instant" product layer, may not be exposed as a stable API model ID. `gpt-5.5` is the closest configured API proxy here.
- Anthropic's `claude-sonnet-4-6` is the configured Claude free-user proxy.
- Gemini's app routing may not exactly match API model names. `gemini-3.5-flash` is configured as the current Flash-style API proxy.

## Install

```bash
cd storytelling_1
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and add API keys for the providers you plan to run.

## Make the request plan

```bash
python run.py plan
```

This writes:

```text
data/request_plan.csv
```

The plan is balanced by replicate: replicate 1 across every provider/prompt, then replicate 2, and so on. This makes partial runs useful if quota or usage limits interrupt the study.

## Run the full study

```bash
python run.py run
```

Run one provider only:

```bash
python run.py run --provider openai
python run.py run --provider anthropic
python run.py run --provider gemini
```

Run a small smoke test:

```bash
python run.py run --max-requests 12
```

Resume after interruption:

```bash
python run.py run
```

Retry rows that were saved as errors:

```bash
python run.py run --retry-errors
```

## Analyze

```bash
python run.py score
python run.py summarize
python run.py export
```

Or do everything after generation:

```bash
python run.py all
```

## Storage design

Primary data store:

```text
data/storytelling_1.sqlite
```

Small analysis outputs:

```text
results/motif_scores.csv
results/prompt_provider_summary.csv
results/title_counts.csv
results/run_status_summary.csv
results/token_usage_summary.csv
results/run_report.md
```

Compressed exports:

```text
data/exports/stories.csv.gz
data/exports/stories_shard_0001.jsonl.gz
...
data/exports/manifest.json
```

The JSONL export is sharded and gzip-compressed so you do not end up with one enormous upload-hostile file.

## Prompt cells

Edit `prompts.yaml` to change prompt text. The current cells are:

1. `tell me a story please`
2. `tell me a story`
3. `write me a story`
4. `tell me a short story please`
5. `tell me a strange story please`
6. `tell me a funny story please`
7. `tell me a story please. First choose a random setting and genre.`
8. `tell me a story please, but not about lighthouses, lamps, the sea, ships, storms, fog, islands, cliffs, or old caretakers.`

## Main outcome flags

`score_motifs.py` creates binary and count fields for:

- lighthouse
- keeper / caretaker / lamplighter
- lamp / lantern / beacon / light
- sea / coast / island / harbor / reef / cliff
- ship / boat / vessel / sailor
- storm / fog / rain / lightning
- old-person language
- forty-years language
- spiral stairs / steps
- repeated pilot phrases like "rocky spit of land," "great lamp," and "sea ... arguing with the shore"

It also creates a compound `has_lighthouse_parable_cluster` flag for the lighthouse/lamp/sea/ship-or-storm structure.

## Suggested workflow for avoiding partial waste

1. Run `python run.py plan`.
2. Run a smoke test: `python run.py run --max-requests 24`.
3. Run `python run.py score && python run.py summarize` to make sure outputs look sane.
4. Run the full study.
5. If one provider hits quota, stop and keep the balanced partial data. Resume later with the same command.
