# storytelling_1 smoke-test review

Source inspected: `storytelling_1.sqlite`

## What was captured

- Rows: 24
- Providers: anthropic, gemini, openai
- Prompt cells: 8
- Replicates present: [np.int64(1)]
- Statuses: {'ok': 24}

## Provider-level smoke metrics

| provider   |   n |   lighthouse_attractor |   avg_output_tokens |   avg_elapsed |   max_tokens_finishes |
|:-----------|----:|-----------------------:|--------------------:|--------------:|----------------------:|
| anthropic  |   8 |                      4 |               646.1 |          17.1 |                     1 |
| gemini     |   8 |                      3 |               141.6 |           7.2 |                     8 |
| openai     |   8 |                      2 |               715.2 |          20.9 |                     1 |

## Key lessons

- This is only a smoke test: one observation per provider × prompt cell, so motif rates are diagnostic, not inferential.
- Gemini returned `FinishReason.MAX_TOKENS` in all 8/8 rows, often after very short outputs. storytelling_2 adds explicit provider-specific max-output handling plus truncation warnings.
- OpenAI and Anthropic could generate long responses under the old cap; for the core motif question, full endings are usually unnecessary. storytelling_2 defaults to `max_output_tokens: 450`.
- Sequential latency was material. storytelling_2 keeps the balanced replicate order but supports controlled concurrency.
- Storing to SQLite worked well. storytelling_2 keeps SQLite as the primary log, then exports compressed CSV/JSONL shards.

## Prompt-level smoke observations

| provider   | model             | prompt_id                | prompt_group               |   output_tokens |   elapsed_seconds | finish_reason           | lighthouse_attractor   | lighthouse   | lamp   | lantern   | sea   | ship_boat   | storm_fog   | clockmaker   |
|:-----------|:------------------|:-------------------------|:---------------------------|----------------:|------------------:|:------------------------|:-----------------------|:-------------|:-------|:----------|:------|:------------|:------------|:-------------|
| openai     | gpt-5.5           | P01_baseline_exact       | baseline                   |             982 |              28.4 | completed               | True                   | False        | False  | False     | True  | False       | True        | True         |
| anthropic  | claude-sonnet-4-6 | P01_baseline_exact       | baseline                   |             472 |              13.5 | end_turn                | True                   | True         | True   | True      | True  | True        | True        | False        |
| gemini     | gemini-3.5-flash  | P01_baseline_exact       | baseline                   |              46 |               7.9 | FinishReason.MAX_TOKENS | False                  | False        | False  | False     | True  | False       | False       | False        |
| openai     | gpt-5.5           | P02_baseline_no_please   | baseline                   |             364 |              11.9 | completed               | True                   | True         | True   | False     | True  | True        | True        | False        |
| anthropic  | claude-sonnet-4-6 | P02_baseline_no_please   | baseline                   |             955 |              25.2 | end_turn                | True                   | True         | True   | True      | True  | True        | True        | False        |
| gemini     | gemini-3.5-flash  | P02_baseline_no_please   | baseline                   |              48 |               7.4 | FinishReason.MAX_TOKENS | True                   | True         | False  | False     | True  | False       | True        | False        |
| openai     | gpt-5.5           | P03_write_variant        | baseline                   |            1184 |              30.4 | completed               | False                  | False        | False  | True      | True  | False       | True        | False        |
| anthropic  | claude-sonnet-4-6 | P03_write_variant        | baseline                   |            1200 |              29.5 | max_tokens              | True                   | True         | False  | False     | True  | True        | True        | False        |
| gemini     | gemini-3.5-flash  | P03_write_variant        | baseline                   |              46 |               7.5 | FinishReason.MAX_TOKENS | False                  | False        | False  | False     | False | False       | False       | False        |
| openai     | gpt-5.5           | P04_short_variant        | baseline                   |             206 |               8.1 | completed               | False                  | False        | False  | False     | False | False       | False       | False        |
| anthropic  | claude-sonnet-4-6 | P04_short_variant        | baseline                   |             236 |               7.9 | end_turn                | True                   | True         | True   | False     | True  | False       | True        | False        |
| gemini     | gemini-3.5-flash  | P04_short_variant        | baseline                   |              68 |               6.8 | FinishReason.MAX_TOKENS | True                   | True         | False  | False     | True  | False       | False       | False        |
| openai     | gpt-5.5           | P05_strange_variant      | mood                       |             803 |              26.4 | completed               | False                  | False        | False  | False     | False | False       | False       | False        |
| anthropic  | claude-sonnet-4-6 | P05_strange_variant      | mood                       |             569 |              16   | end_turn                | False                  | False        | False  | False     | False | False       | False       | False        |
| gemini     | gemini-3.5-flash  | P05_strange_variant      | mood                       |              45 |               7.2 | FinishReason.MAX_TOKENS | False                  | False        | False  | False     | False | False       | False       | False        |
| openai     | gpt-5.5           | P06_funny_variant        | mood                       |             217 |               7.1 | completed               | False                  | False        | False  | False     | False | False       | False       | False        |
| anthropic  | claude-sonnet-4-6 | P06_funny_variant        | mood                       |             309 |               8.2 | end_turn                | False                  | False        | False  | False     | False | False       | False       | False        |
| gemini     | gemini-3.5-flash  | P06_funny_variant        | mood                       |             326 |               7.2 | FinishReason.MAX_TOKENS | False                  | False        | False  | False     | False | False       | False       | False        |
| openai     | gpt-5.5           | P07_random_setting_genre | intervention_randomization |            1200 |              33.7 | incomplete              | False                  | False        | False  | True      | True  | False       | True        | True         |
| anthropic  | claude-sonnet-4-6 | P07_random_setting_genre | intervention_randomization |             696 |              17.9 | end_turn                | False                  | False        | True   | False     | False | False       | True        | True         |
| gemini     | gemini-3.5-flash  | P07_random_setting_genre | intervention_randomization |             481 |               7.2 | FinishReason.MAX_TOKENS | True                   | False        | False  | False     | True  | False       | True        | False        |
| openai     | gpt-5.5           | P08_suppression          | intervention_suppression   |             766 |              20.7 | completed               | False                  | False        | False  | False     | False | False       | False       | False        |
| anthropic  | claude-sonnet-4-6 | P08_suppression          | intervention_suppression   |             732 |              18.7 | end_turn                | False                  | False        | False  | False     | False | False       | False       | False        |
| gemini     | gemini-3.5-flash  | P08_suppression          | intervention_suppression   |              73 |               6.8 | FinishReason.MAX_TOKENS | False                  | False        | False  | False     | False | False       | False       | False        |