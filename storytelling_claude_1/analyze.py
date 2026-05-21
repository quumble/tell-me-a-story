#!/usr/bin/env python3
"""
analyze.py — discover story attractors and report three similarity signals.

Usage:
    python analyze.py                      # analyze every prompt cell
    python analyze.py --prompt P01_baseline_please
    python analyze.py --min-cluster 4      # min stories to call it an attractor
    python analyze.py --tightness 0.35     # how alike stories must be to group
    python analyze.py --model all-mpnet-base-v2  # heavier, max-quality embeddings
    python analyze.py --tfidf              # skip embeddings, cluster on TF-IDF

An "attractor" is a cluster of stories within a prompt cell that are much more
similar to each other than stories usually are. The lighthouse parable was the
first one we noticed; this finds it AND whatever else is lurking, without being
told what to look for.

For every discovered cluster we report THREE signals, because "these are the
same story" can mean three different things:

  1. semantic     — overall meaning similarity (sentence embeddings, cosine).
                    Catches "same story, totally different words" (a lighthouse
                    keeper vs a desert well-tender who are the same parable).
  2. phrase       — verbatim 2-3 gram overlap (TF-IDF). Catches reused wording
                    like "rocky spit of land".
  3. setting      — shared who/where/object lexicon. Names the trope.

Clustering uses signal #1 (semantic) by default — it's the most robust. The
other two are reported so you can see WHICH kind of sameness drove each cluster.

We also keep one named `is_lighthouse` flag as a known baseline.

Dependencies (analysis-time only; never touched during a collection run):
  required: numpy, scikit-learn
  best results: sentence-transformers + torch (auto-used if installed;
                the default model is small (~80MB). Falls back to TF-IDF
                clustering with a warning if the library isn't installed.)
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE = Path(__file__).resolve().parent

# Default embedding model. all-MiniLM-L6-v2 is small (~80MB), fast, and close
# enough to the heavier models for clustering stories by similarity. For maximum
# quality on subtle distinctions, pass --model all-mpnet-base-v2 (~420MB).
DEFAULT_MODEL = "all-MiniLM-L6-v2"

# Read the output-token cap(s) from config so truncation detection tracks
# whatever the run actually used. Providers may override the global cap, so we
# build a {provider: cap} map. Falls back to a large number if unavailable.
def _load_token_caps():
    try:
        import yaml
        with open(BASE / "config.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        global_cap = int(cfg.get("max_output_tokens", 100000))
        caps = {}
        for name, p in (cfg.get("providers") or {}).items():
            caps[name] = int((p or {}).get("max_output_tokens", global_cap))
        return global_cap, caps
    except Exception:
        return 100000, {}

GLOBAL_TOKEN_CAP, TOKEN_CAPS = _load_token_caps()


def _cap_for(provider):
    return TOKEN_CAPS.get(provider, GLOBAL_TOKEN_CAP)


def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

# The one named attractor we already know about, kept as a stable baseline.
LIGHTHOUSE = re.compile(
    r"\blight\s?house\b|\bkeeper\b|\bbeacon\b|\blamplighter\b", re.IGNORECASE)

# Lexicon for the "setting" signal — who / where / what recurs. Not used to
# score; only to describe and name a discovered cluster.
SETTING_WORDS = [
    "keeper", "lighthouse", "lamplighter", "clockmaker", "watchmaker", "baker",
    "fisherman", "sailor", "captain", "witch", "wizard", "king", "queen",
    "princess", "knight", "dragon", "fox", "rabbit", "owl", "bear", "child",
    "girl", "boy", "grandmother", "grandfather", "hermit", "monk", "astronaut",
    "robot", "gardener", "painter", "musician", "librarian", "cartographer",
    "mapmaker", "shepherd", "miller", "blacksmith", "well", "tender",
    "village", "town", "forest", "mountain", "sea", "ocean", "island", "desert",
    "castle", "tower", "cottage", "harbor", "harbour", "valley", "city",
    "station", "spaceship", "garden", "library", "shop", "cave", "river",
    "meadow", "kingdom", "lamp", "lantern", "clock", "map", "letter", "key",
    "mirror", "book", "seed", "star", "moon", "candle", "bell", "thread", "music",
]
SETTING_RE = {w: re.compile(rf"\b{w}s?\b", re.IGNORECASE) for w in set(SETTING_WORDS)}


# --------------------------------------------------------------------------- #
# Embedding backend (optional). Loaded once, reused across cells.
# --------------------------------------------------------------------------- #
class Embedder:
    """Lazy sentence-transformers wrapper with a TF-IDF fallback flag."""

    def __init__(self, model_name, force_tfidf=False):
        self.ok = False
        self.model = None
        if force_tfidf:
            print("Using TF-IDF for clustering (--tfidf).")
            return
        try:
            from sentence_transformers import SentenceTransformer
            print(f"Loading embedding model '{model_name}' "
                  f"(first run downloads it)...")
            self.model = SentenceTransformer(model_name)
            self.ok = True
        except Exception as exc:
            print(f"NOTE: sentence-transformers unavailable ({type(exc).__name__}). "
                  f"Falling back to TF-IDF clustering.\n"
                  f"      For best results: pip install sentence-transformers",
                  file=sys.stderr)

    def similarity(self, texts):
        """Return an n x n cosine-similarity matrix for a cell's stories."""
        if self.ok:
            emb = self.model.encode(texts, normalize_embeddings=True,
                                    show_progress_bar=False)
            return cosine_similarity(emb)
        # TF-IDF fallback.
        vec = TfidfVectorizer(lowercase=True, stop_words="english",
                              ngram_range=(1, 3), min_df=2, max_features=4000)
        try:
            X = vec.fit_transform(texts)
        except ValueError:
            return None
        return cosine_similarity(X)


# --------------------------------------------------------------------------- #
# Per-cell signal helpers (always TF-IDF / lexicon based, for interpretability)
# --------------------------------------------------------------------------- #
def phrase_similarity(texts):
    """Mean pairwise 2-3 gram cosine similarity within a set of stories."""
    if len(texts) < 2:
        return 0.0
    vec = TfidfVectorizer(lowercase=True, stop_words="english",
                          ngram_range=(2, 3), min_df=2, max_features=2000)
    try:
        X = vec.fit_transform(texts)
    except ValueError:
        return 0.0
    sim = cosine_similarity(X)
    n = len(texts)
    off = (sim.sum() - n) / (n * (n - 1)) if n > 1 else 0.0
    return float(max(0.0, off))


def fingerprint_phrases(texts, k=6):
    """The 2-3 grams most characteristic of a set of stories."""
    if len(texts) < 2:
        return []
    vec = TfidfVectorizer(lowercase=True, stop_words="english",
                          ngram_range=(2, 3), min_df=2, max_features=2000)
    try:
        X = vec.fit_transform(texts)
    except ValueError:
        return []
    scores = np.asarray(X.mean(axis=0)).ravel()
    vocab = np.array(vec.get_feature_names_out())
    top = scores.argsort()[::-1][:k]
    return [vocab[i] for i in top if scores[i] > 0]


def setting_summary(texts, k=5):
    """Most common setting/role/object words, with the share of stories using each."""
    counts = Counter()
    for t in texts:
        for w, rx in SETTING_RE.items():
            if rx.search(t):
                counts[w] += 1
    n = len(texts)
    return [(w, round(c / n, 2)) for w, c in counts.most_common(k)]


def setting_overlap(texts):
    """A 0-1 score: how concentrated the setting vocabulary is across the cluster.
    High = the same handful of who/where words appear in most stories."""
    if not texts:
        return 0.0
    top = setting_summary(texts, k=3)
    return round(sum(s for _, s in top) / 3.0, 2) if top else 0.0


# --------------------------------------------------------------------------- #
# Clustering
# --------------------------------------------------------------------------- #
def cluster_cell(texts, embedder, min_cluster, tightness):
    """Cluster one cell. Returns labels (label -1 = not in any attractor)."""
    n = len(texts)
    if n < min_cluster:
        return [-1] * n
    sim = embedder.similarity(texts)
    if sim is None:
        return [-1] * n
    dist = 1.0 - sim
    np.fill_diagonal(dist, 0.0)
    dist[dist < 0] = 0.0
    model = AgglomerativeClustering(
        n_clusters=None, metric="precomputed",
        linkage="average", distance_threshold=tightness)
    raw = model.fit_predict(dist)
    sizes = Counter(raw)
    keep = {c for c, sz in sizes.items() if sz >= min_cluster}
    return [c if c in keep else -1 for c in raw]


def read_ok_stories(path):
    if not path.exists():
        raise SystemExit(f"No data at {path}. Run `python run.py` first.")
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("status") == "ok"]
    if not rows:
        raise SystemExit("No successful stories to analyze yet.")
    return rows


def main():
    ap = argparse.ArgumentParser(description="Discover story attractors.")
    ap.add_argument("--prompt", help="analyze only this prompt_id")
    ap.add_argument("--min-cluster", type=int, default=3,
                    help="min stories for a cluster to count as an attractor")
    ap.add_argument("--tightness", type=float, default=None,
                    help="distance cut; lower = stricter. Defaults: 0.35 for "
                         "embeddings, 0.55 for TF-IDF.")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"sentence-transformers model (default {DEFAULT_MODEL})")
    ap.add_argument("--tfidf", action="store_true",
                    help="cluster on TF-IDF instead of embeddings")
    args = ap.parse_args()

    rows = read_ok_stories(BASE / "data" / "stories.csv")
    if args.prompt:
        rows = [r for r in rows if r["prompt_id"] == args.prompt]
        if not rows:
            raise SystemExit(f"No stories for prompt {args.prompt}.")

    embedder = Embedder(args.model, force_tfidf=args.tfidf)
    using_embeddings = embedder.ok
    tightness = args.tightness
    if tightness is None:
        tightness = 0.35 if using_embeddings else 0.55

    # Group by (provider, prompt) so we compare like with like.
    cells = {}
    for r in rows:
        cells.setdefault((r["provider"], r["prompt_id"]), []).append(r)

    attractor_rows, scored_rows = [], []
    cluster_uid = 0

    print(f"\nAnalyzing {len(rows)} stories across {len(cells)} cells "
          f"(signal={'embeddings' if using_embeddings else 'tfidf'}, "
          f"min_cluster={args.min_cluster}, tightness={tightness}).\n")

    for (prov, pid), cell in sorted(cells.items()):
        texts = [r.get("story_text", "") or "" for r in cell]
        labels = cluster_cell(texts, embedder, args.min_cluster, tightness)

        for r, lab in zip(cell, labels):
            # A story whose output_tokens nearly hit the cap was likely cut off
            # mid-sentence. Flag it so a short truncated story isn't mistaken for
            # a model that naturally writes short. (Heuristic: within 3 of cap.)
            out_tok = _as_int(r.get("output_tokens"))
            truncated = (out_tok is not None and out_tok >= _cap_for(prov) - 3)
            text = r.get("story_text", "") or ""
            wc = len(text.split())
            thoughts = _as_int(r.get("thoughts_tokens"))
            # A genuinely unusable output: almost no words. Usually means the
            # provider spent its budget on reasoning (thinking tokens) and left
            # no room for the story — the Gemini failure mode we hit.
            too_short = wc < 15
            scored_rows.append({
                "request_id": r["request_id"], "provider": prov,
                "prompt_id": pid, "replicate": r.get("replicate", ""),
                "local_cluster": lab,
                "is_lighthouse": bool(LIGHTHOUSE.search(text)),
                "word_count": wc,
                "output_tokens": out_tok if out_tok is not None else "",
                "thoughts_tokens": thoughts if thoughts is not None else "",
                "finish_reason": r.get("finish_reason", ""),
                "likely_truncated": truncated,
                "too_short_unusable": too_short,
            })

        # Per-cluster, compute all three signals.
        sim_full = embedder.similarity(texts) if any(l != -1 for l in labels) else None
        for lab in sorted(set(labels)):
            if lab == -1:
                continue
            idx = [i for i, l in enumerate(labels) if l == lab]
            members = [texts[i] for i in idx]
            cluster_uid += 1

            # Signal 1: semantic similarity within the cluster (mean off-diagonal).
            if sim_full is not None:
                sub = sim_full[np.ix_(idx, idx)]
                m = len(idx)
                semantic = float((sub.sum() - m) / (m * (m - 1))) if m > 1 else 0.0
            else:
                semantic = 0.0

            attractor_rows.append({
                "cluster_uid": cluster_uid, "provider": prov, "prompt_id": pid,
                "size": len(members), "cell_n": len(cell),
                "share": round(len(members) / len(cell), 3),
                "sig_semantic": round(max(0.0, semantic), 2),
                "sig_phrase": round(phrase_similarity(members), 2),
                "sig_setting": setting_overlap(members),
                "lighthouse_share": round(
                    sum(bool(LIGHTHOUSE.search(t)) for t in members) / len(members), 3),
                "setting_words": " | ".join(f"{w}({s})" for w, s in setting_summary(members)),
                "fingerprint_phrases": " | ".join(fingerprint_phrases(members)),
            })

    # ---- write CSVs ----
    (BASE / "data").mkdir(exist_ok=True)
    with open(BASE / "data" / "attractors.csv", "w", encoding="utf-8", newline="") as f:
        cols = ["cluster_uid", "provider", "prompt_id", "size", "cell_n", "share",
                "sig_semantic", "sig_phrase", "sig_setting", "lighthouse_share",
                "setting_words", "fingerprint_phrases"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(attractor_rows)
    with open(BASE / "data" / "scored.csv", "w", encoding="utf-8", newline="") as f:
        cols = ["request_id", "provider", "prompt_id", "replicate",
                "local_cluster", "is_lighthouse", "word_count",
                "output_tokens", "thoughts_tokens", "finish_reason",
                "likely_truncated", "too_short_unusable"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(scored_rows)

    # ---- console report ----
    if not attractor_rows:
        print("No attractors found. Try a looser --tightness or smaller --min-cluster.")
    else:
        print("Each cluster shows three 'same story' signals (0-1):")
        print("  sem = semantic meaning | phr = verbatim phrasing | set = shared setting\n")
        for a in sorted(attractor_rows, key=lambda x: x["share"], reverse=True):
            tag = "  [lighthouse]" if a["lighthouse_share"] >= 0.5 else ""
            print(f"{a['provider']:<9} {a['prompt_id']:<20} "
                  f"{a['size']}/{a['cell_n']} ({a['share']:.0%}){tag}")
            print(f"    signals:  sem={a['sig_semantic']:.2f}  "
                  f"phr={a['sig_phrase']:.2f}  set={a['sig_setting']:.2f}")
            if a["setting_words"]:
                print(f"    trope:    {a['setting_words']}")
            if a["fingerprint_phrases"]:
                print(f"    phrases:  {a['fingerprint_phrases']}")
            print()

    lh = sum(s["is_lighthouse"] for s in scored_rows)
    print(f"Lighthouse baseline: {lh}/{len(scored_rows)} stories "
          f"({lh / len(scored_rows):.0%}) mention a lighthouse/keeper/beacon.")
    trunc = sum(1 for s in scored_rows if s["likely_truncated"])
    if trunc:
        print(f"Truncated at cap: {trunc}/{len(scored_rows)} "
              f"({trunc / len(scored_rows):.0%}) hit their provider's token cap "
              f"— expected with a tight cap; the attractor signal is in the "
              f"opening, so this is fine for clustering.")

    # Loud data-quality alarm: unusable (near-empty) outputs, broken out by
    # provider. This is the failure that nearly cost a full run — surface it.
    bad = [s for s in scored_rows if s["too_short_unusable"]]
    if bad:
        from collections import Counter
        by_prov = Counter(s["provider"] for s in bad)
        print(f"\n!!! DATA QUALITY: {len(bad)}/{len(scored_rows)} outputs are "
              f"too short to use (<15 words). By provider: {dict(by_prov)}.")
        # If a provider also burned thinking tokens, name the likely cause.
        thinky = [s for s in bad if _as_int(s.get("thoughts_tokens"))]
        if thinky:
            print("    Some had nonzero thoughts_tokens — reasoning likely ate "
                  "the budget. Check that thinking is disabled for that provider.")
        print("    These rows are flagged too_short_unusable=True in scored.csv. "
              "Investigate before trusting per-provider rates.")
    print("\nWrote data/attractors.csv and data/scored.csv")


if __name__ == "__main__":
    main()
