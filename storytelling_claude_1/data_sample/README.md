# data_sample

`stories_sample.csv` is a tiny, illustrative slice of a real run — one row per
(provider × prompt) cell, with `story_text` truncated to ~200 characters so the
file stays small. It exists only to show the **column shape** of the data that
`run.py` writes and `analyze.py` reads.

It is not a research artifact. The full run output lives in `../data/stories.csv`
(not committed) and is regenerable with `python run.py`.
