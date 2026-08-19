# OCR Accuracy Benchmark 2026 — Methodology

Publisher: FactScan AI. Study version 1.0. Published 2026-08-18.
Canonical page: https://factscanai.app/research/ocr-accuracy-benchmark

## Study type

API-level OCR degradation benchmark on synthetic documents with exact ground truth.
This is not an end-to-end camera or mobile-app benchmark, and it is not a cross-provider comparison.

## Dataset

- 60 synthetic documents, generated with a fixed seed and frozen before any OCR call.
- Categories: 15 prose, 15 table, 15 invoice, 15 mixed-layout.
- Languages: 36 English / 24 Czech (9 EN / 6 CS per category).
- Fictional entities only; no real people, companies, accounts or third-party copyrighted text.
- Deterministic variation across font family, font size, line and paragraph length, page density,
  column width, table structure, row count, invoice layout, alignment, heading structure, numeric
  content, Czech diacritic density and punctuation.
- Ground truth is exact by construction: each page is rendered from a known string and that string
  is the ground truth.
- A manifest records category, language, dimensions, generation parameters and a SHA-256 for every
  source image and ground-truth file (`dataset-manifest.json`).

## Degradation ladders (frozen before execution)

- Blur (deterministic Gaussian): baseline, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0 px — 7 x 60 = 420 variants.
- Resolution (downscale only, no upscale before submission): 100%, 25%, 20%, 18%, 16%, 15%, 14%,
  12%, 10% of original linear scale — 8 x 60 = 480 variants (the 100% level is the blur baseline,
  OCR'd once and reused).
- Total planned provider calls: 60 + 360 + 480 = 900.

## OCR path

Google Vision TEXT_DETECTION through FactScan's production API-level OCR path.
No language hint, no provider fallback, no AI cleanup, no semantic retry, no manual correction.

## Normalization (frozen)

NFC, fold typographic quotes and dashes, strip soft hyphens, deterministic line-break hyphenation
rejoin, collapse all whitespace to a single ASCII space, trim. Case and punctuation are preserved.

## Metrics and definitions

- CER / WER — strict sequence metrics; CER is primary.
- Exact = CER 0.0. Near-exact = CER <= 0.02.
- Document failure = CER > 0.30 (predefined before execution).
- Empty failure = successful response with no recognized text. Scored CER 1.0. Never retried.
- Silent non-empty failure = successful response with non-empty text and CER > 0.30, described as
  "non-empty but materially inaccurate". The provider exposes no confidence data on this path, so
  no confidence claim is made anywhere.
- Content F1 = order-tolerant token-multiset precision / recall / F1 (duplicates counted), computed
  for table, invoice and mixed documents and reported alongside strict CER, never replacing it.

## Statistics

Per condition: mean, median, p25, p75, min, max, exact and near-exact counts, failure rate, empty
failure rate, silent failure rate. Failure rates carry Wilson 95% confidence intervals. Paired
analysis against each document's own baseline reports median paired delta CER with a bootstrap 95%
confidence interval. No p-values are reported. Outliers are retained in every headline number.

## Execution accounting

900 planned calls, 900 persisted responses (100%), 0 transport or provider errors, 0 retries,
0 HTTP non-200 responses. No variant is imputed, dropped or estimated.

## Limitations

Synthetic renders only; n = 60; two languages; API-level rather than a full camera/app workflow;
a single OCR provider; Gaussian blur is a controlled degradation and is not identical to every
real-world camera blur; no real-phone capture arm; no claim of universal thresholds across OCR
engines; the sharpness bridge metric did not support a single universal absolute threshold.
