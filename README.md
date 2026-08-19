# FactScan OCR Accuracy Benchmark 2026 — Reproducibility Repository

[![License: MIT](https://img.shields.io/badge/scripts-MIT-blue.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-green.svg)](DATA_LICENSE.md)

This repository is the **reproducibility companion** to the canonical
benchmark report published at:

> **https://factscanai.app/research/ocr-accuracy-benchmark**

It contains the published study data, the frozen scoring methodology, and
zero-credential scripts that reproduce every aggregate figure cited in the
report directly from the per-variant CSV. **No OCR provider calls are made and
no credentials are required to reproduce these results.**

---

## What this repository is

A single-provider, API-level benchmark of how OCR text-recognition accuracy
degrades as capture quality degrades, on 60 synthetic documents with exact
ground truth, across a blur ladder (2.5–5.0 px Gaussian) and a resolution
ladder (25%–10% of original linear scale): **900 OCR executions, 0 transport
errors, 0 retries, 100% completeness**.

| | |
|---|---|
| Documents | 60 (15 prose / 15 table / 15 invoice / 15 mixed) |
| Languages | 36 English / 24 Czech |
| OCR executions | 900 |
| Transport errors | 0 |
| Retries | 0 |
| Completeness | 900 / 900 (100%) |
| Date of completion | 2026-08-18 |
| Study version | 1.0 |

---

## Three strongest supported findings

1. **The blur cliff is sharp and reproducible.** Text recognition is
   effectively lossless up to `3.0` px Gaussian blur (median CER `0.0046`),
   then fails fast: `36.7%` of documents fail at `4.0` px and `75.0%` at
   `5.0` px (median CER `0.1574` and `0.8302`).

2. **The resolution knee sits at 16–18% of original linear scale.** Median
   CER triples from `0.0943` (`18%`) to `0.2799` (`16%`) and the failure rate
   jumps from `20.0%` to `46.7%` with non-overlapping Wilson intervals
   (`[0.1183, 0.3178]` vs `[0.3463, 0.5911]`). Relative scale generalizes
   across page sizes far better than total pixel count (CV `0.245` vs
   `0.598`).

3. **Degraded-capture OCR fails silently, not loudly.** Across every
   condition a user would plausibly submit, `90–100%` of failures return
   non-empty, materially inaccurate text. Empty responses only dominate
   below `12%` scale (`51.7%` empty at `10%`).

Supporting: strict CER alone overstates baseline error on tables and invoices
— `3` of `3` baseline structured failures were pure reading-order artifacts
with content F1 `1.000`.

---

## Repository structure

```text
factscan-ocr-benchmark/
├── README.md                  # this file — headline figures + how to reproduce
├── CITATION.cff               # CFF 1.2.0 citation metadata
├── LICENSE                    # MIT (scripts + scaffolding)
├── DATA_LICENSE.md            # CC BY 4.0 (datasets)
├── requirements.txt           # Python dependencies (stdlib-only: zero)
├── methodology/
│   └── methodology.md         # frozen study protocol & definitions
├── data/
│   ├── summary.json            # headline summary + scope
│   ├── methodology.md         # methodology text (published)
│   ├── dataset-manifest.json   # 60-doc manifest with SHA-256 hashes (no GT strings)
│   ├── condition-aggregates.json
│   ├── failure-modes.json
│   ├── baseline-gate.json
│   ├── outliers.json
│   ├── per-variant.csv         # 900 rows — primary reproduction input
│   ├── paired-deltas.csv
│   ├── resolution-manifest.json
│   └── sharpness-metrics.json
├── scripts/
│   ├── metrics.py              # frozen normalization + CER/WER/F1 + agg()
│   ├── reproduce_metrics.py   # recompute all aggregates from per-variant.csv
│   └── consistency_check.py   # gate: every README figure traces to data
└── charts/
    ├── chart1_blur.png
    ├── chart2_resolution.png
    ├── chart3_failure_modes.png
    └── chart4_sharpness_cer.png
```

---

## Reproducing the results

The scripts are **pure Python 3 with no third-party dependencies** — only the
standard library is used.

```bash
# 1. Reproduce every published aggregate from the per-variant CSV.
#    Recomputes condition-aggregates, failure-modes, baseline-gate,
#    outliers, paired-deltas and diffs them against the canonical JSON.
python3 scripts/reproduce_metrics.py

# 2. Gate: confirm every number cited in this README traces to the data.
python3 scripts/consistency_check.py
```

Both scripts exit `0` on success and non-zero on any divergence (tolerance
`1e-4` for floating-point values). `reproduce_metrics.py` is the stronger
check: it recomputes the full aggregate tree from `data/per-variant.csv` and
byte-compares it against the published `condition-aggregates.json`,
`failure-modes.json`, `baseline-gate.json`, and `outliers.json`.

### Applying the scoring to your own OCR output

`scripts/metrics.py` exposes the frozen `normalize()`, `cer()`, `wer()`, and
`content_score()` functions so the same definitions can be applied to new
ground-truth / OCR-output pairs:

```python
import sys; sys.path.insert(0, "scripts")
from metrics import cer, wer, content_score

gt = "The quick brown fox."
ocr = "The quick brown fox."
print(cer(gt, ocr))           # 0.0
print(wer(gt, ocr))           # 0.0
p, r, f1 = content_score(gt, ocr)
print(f1)                      # 1.0
```

---

## Methodology (summary)

- **Dataset:** 60 synthetic documents, generated with a fixed seed and frozen
  before any OCR call. 15 each of prose / table / invoice / mixed-layout;
  36 English / 24 Czech. Fictional entities only. Ground truth is exact by
  construction — each page is rendered from a known string and that string is
  the ground truth. `dataset-manifest.json` carries SHA-256 hashes for every
  source image and ground-truth file; **no ground-truth text strings are
  included in this repository.**
- **Conditions:** blur ladder 2.5 / 3.0 / 3.5 / 4.0 / 4.5 / 5.0 px (7 × 60 =
  420) and resolution ladder 25 / 20 / 18 / 16 / 15 / 14 / 12 / 10 % (8 × 60 =
  480), plus the shared baseline (60). Total 900.
- **Normalization (frozen before the run):** NFC, fold typographic
  quotes/dashes, strip soft hyphens, deterministic line-break hyphenation
  rejoin, collapse all whitespace to a single ASCII space, trim. Case and
  punctuation preserved.
- **Metrics:** CER / WER (strict, primary); exact = CER 0.0; near-exact =
  CER ≤ 0.02; document failure = CER > 0.30; empty failure = successful
  response with no recognized text (scored CER 1.0); silent failure =
  non-empty text, CER > 0.30; content F1 = order-tolerant token-multiset
  precision/recall/F1 for structured documents.
- **No threshold, normalization rule or taxonomy was changed after seeing
  results. No manual quality judgement is used anywhere.**

See `methodology/methodology.md` and `data/methodology.md` for the full
protocol.

---

## What is *not* established

- No universal absolute variance-of-Laplacian sharpness threshold (best Youden
  J `0.505`, heavy distribution overlap).
- No claim about provider confidence, real photographs, handwriting,
  non-Latin scripts, or cross-provider comparison.

---

## Citation

If you use this dataset or benchmark in your work, please cite it using the
metadata in `CITATION.cff`:

```bibtex
@dataset{factscan_ocr_benchmark_2026,
  title       = {FactScan OCR Accuracy Benchmark 2026},
  author      = {{FactScan AI}},
  year        = {2026},
  version     = {1.0.0},
  date        = {2026-08-19},
  url         = {https://factscanai.app/research/ocr-accuracy-benchmark},
  repository  = {https://github.com/FactScanAI/factscan-ocr-benchmark}
}
```

---

## License

- **Scripts and scaffolding** (`scripts/`, `README.md`, `CITATION.cff`,
  `methodology/`): [MIT License](LICENSE).
- **Datasets and result artifacts** (`data/`, `charts/`):
  [CC BY 4.0](DATA_LICENSE.md).

---

## Contact

This repository is maintained by **FactScan AI** as a reproducibility
companion to the canonical report at
<https://factscanai.app/research/ocr-accuracy-benchmark>. The canonical
report is the authoritative source; this repository exists to make the
underlying data and scoring independently verifiable.
