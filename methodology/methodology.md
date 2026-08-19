# FactScan OCR Accuracy Benchmark 2026 — Methodology

This is the frozen study protocol, mirrored from the canonical report at
<https://factscanai.app/research/ocr-accuracy-benchmark>. The `data/`
directory also contains a copy as `methodology.md`. No threshold,
normalization rule, or taxonomy was changed after results were observed.

## 1. Study scope

Single-provider, API-level benchmark of OCR text-recognition accuracy under
controlled capture-quality degradation, using synthetic documents with exact
ground truth. This is **not** an end-to-end camera or application benchmark;
it isolates the OCR recognition path from capture, perspective correction,
and post-processing.

## 2. Dataset

60 synthetic documents, generated with a fixed seed and frozen before any OCR
call: 15 prose, 15 table, 15 invoice, 15 mixed-layout; 36 English / 24 Czech
(9 EN / 6 CS per category). Fictional entities only. Ground truth is exact by
construction — each page is rendered from a known string and that string is the
ground truth. Deterministic variation across font family, size, line and
paragraph length, density, column width, table structure, row count, invoice
layout, alignment, heading structure, numeric content, Czech diacritic
density, and punctuation. The manifest (`dataset-manifest.json`) carries
SHA-256 hashes for every source image and ground-truth file. **Ground-truth
text strings are not included in this repository** — only character/line
counts and hashes — so the scoring cannot be re-run from raw text here, but
all aggregate metrics can be reproduced from `per-variant.csv`.

## 3. Conditions

- **Blur ladder** (deterministic Gaussian): baseline, 2.5, 3.0, 3.5, 4.0, 4.5,
  5.0 px — 7 × 60 = 420.
- **Resolution ladder** (downscale only, no upscale before submission): 100%,
  25, 20, 18, 16, 15, 14, 12, 10% — the 100% level is the blur baseline,
  OCR'd once and reused; 8 × 60 = 480.
- Total 60 + 360 + 480 = 900.

## 4. Execution accounting

| Item | Value |
|---|---|
| Planned provider calls | 900 |
| Transport/provider errors | 0 |
| Retries consumed | 0 |
| Final persisted raw responses | 900 / 900 (100%) |
| HTTP non-200 responses | 0 |
| Responses with attempts > 1 | 0 |

Completeness is total; no variant is imputed, dropped, or estimated.

## 5. Scoring and frozen definitions

Normalization (frozen before the run): NFC, fold typographic quotes/dashes,
strip soft hyphens, deterministic line-break hyphenation rejoin, collapse all
whitespace to a single ASCII space, trim. Case and punctuation preserved.

- **CER / WER** — strict sequence metrics, primary.
- **Exact** = CER 0.0; **near-exact** = CER ≤ 0.02.
- **Document failure** = CER > 0.30.
- **Empty failure** = successful response, no recognized text. Scored CER 1.0.
  Never retried.
- **Silent failure** = successful response, non-empty text, CER > 0.30
  ("non-empty but materially inaccurate"). The provider exposes no confidence
  data on this path, so no confidence claim is made anywhere.
- **Content F1** — order-tolerant token-multiset precision/recall/F1
  (duplicates counted), for table / invoice / mixed documents. Reported
  alongside strict CER, never replacing it.

The frozen normalization and metric functions are in `scripts/metrics.py`.
No threshold, normalization rule, or taxonomy was changed after seeing
results. No manual quality judgement is used anywhere.

## 6. Reproducing

```bash
python3 scripts/reproduce_metrics.py   # recompute all aggregates from per-variant.csv
python3 scripts/consistency_check.py   # gate every README figure against the data
```

Both are standard-library-only and require no credentials.
