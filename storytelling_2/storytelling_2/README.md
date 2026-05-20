# storytelling_2

`storytelling_2` is a clean, separate follow-up to the original `storytelling_1` smoke test.

The question is not whether models can write stories. The question is whether vague cold prompts like:

```text
tell me a story please
```

collapse into recurring default story attractors, especially lighthouse / lamp / keeper / sea / storm parables.

## What changed after storytelling_1

The uploaded `storytelling_1.sqlite` smoke test contained 24 rows: 8 prompt cells × 3 providers × 1 replicate.

Lessons incorporated here:

1. **Output cap reduced.** We usually need the opening/title/motif, not the entire ending. Default `max_output_tokens` is now 450.
2. **Gemini truncation check added.** In `storytelling_1`, Gemini finished with `MAX_TOKENS` in all 8/8 rows, often after extremely short outputs. This project summarizes truncation rates so provider-specific cap problems are visible before the full run.
3. **SQLite-first storage kept.** Giant JSONLs are avoided. Raw-ish capped responses go into SQLite first, then compressed CSV/JSONL shards are exported.
4. **Balanced run order kept.** The runner iterates by replicate across all provider/prompt cells, so interrupted runs leave usable partial data.
5. **Concurrency is built in.** Use `--concurrency 6` or lower if rate limits appear.
6. **Suppression is separated analytically.** The explicit "not about lighthouses..." prompt is included, but summaries keep it identifiable as an intervention rather than a spontaneous baseline.

## Model proxies

The defaults follow the prior "average free-user interface behavior" proxy plan:

| Provider | Default API model |
|---|---|
| OpenAI | `gpt-5.5` |
| Anthropic | `claude-sonnet-4-6` |
| Gemini | `gemini-3.5-flash` |

Model IDs can change. Check provider docs before a full run and edit `study_config.yaml` if needed.

## Study size

Default:

```text
8 prompts × 3 providers × n=100 = 2,400 planned stories
```

The output cap is 450 tokens, so the run is much cheaper and faster than uncapped full stories.

## Setup: PowerShell

```powershell
cd storytelling_2

python -m venv .venv

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

Copy-Item .env.example .env
notepad .env
```

Or skip activation and use:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py plan
```

## Smoke test

Create the plan:

```powershell
python run.py plan
```

Run one balanced replicate:

```powershell
python run.py run --max-requests 24 --concurrency 6
python run.py score
python run.py summarize
python run.py status
```

Read:

```text
results/summary.md
```

If a provider has a high truncation rate or strange output-token counts, stop and fix config before scaling.

## Full run

```powershell
python run.py run --concurrency 6
```

Resume after interruption:

```powershell
python run.py run --concurrency 6
```

Retry rows that ended with errors:

```powershell
python run.py run --retry-errors --concurrency 3
```

## Exports

```powershell
python run.py score
python run.py summarize
python run.py export
```

Outputs:

```text
data/storytelling_2.sqlite
data/exports/stories.csv.gz
data/exports/motif_scores.csv.gz
data/exports/stories_shard_0001.jsonl.gz
results/summary.md
results/prompt_provider_motif_rates.csv
results/provider_motif_rates.csv
results/title_counts.csv
```

## Notes on interpretation

- Baseline prompts estimate spontaneous attractor behavior.
- Mood prompts test whether the attractor survives mild semantic steering.
- Random-setting prompt tests whether explicit diversification breaks the attractor.
- Suppression prompt tests instruction-following against the known attractor; do not pool it with spontaneous baseline rates.
- The motif scorer is intentionally simple and deterministic. It is a screening tool, not a final human-coded dataset.
