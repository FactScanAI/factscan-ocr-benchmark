"""Frozen scoring for the FactScan OCR Accuracy Benchmark 2026.

Path-independent port of the harness `score.py` used in the 60-document
validation study. Normalization is frozen: NFC -> fold typographic
quotes/dashes -> remove soft hyphens -> deterministic line-break hyphenation
rejoin -> collapse all whitespace to one ASCII space -> trim. Case and
punctuation preserved.

This module exposes the normalization and metric functions so that the same
definitions can be applied to new OCR outputs. `reproduce_metrics.py` consumes
the published per-variant data and recomputes the study aggregates using the
`agg()` function below.
"""
import collections
import math
import random
import re
import statistics
import unicodedata

FAILURE_CER = 0.30
NEAR_CER = 0.02

BLUR_CONDS = ["blur_2_5", "blur_3_0", "blur_3_5", "blur_4_0", "blur_4_5", "blur_5_0"]
RES_CONDS = ["res_25", "res_20", "res_18", "res_16", "res_15", "res_14", "res_12", "res_10"]
CONDITIONS = ["baseline"] + BLUR_CONDS + RES_CONDS
STRUCTURED = {"table", "invoice", "mixed"}

QUOTE_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2013": "-", "\u2014": "-", "\u2010": "-", "\u2011": "-",
    "\u00ab": '"', "\u00bb": '"', "\u2039": "'", "\u203a": "'",
}


def normalize(s):
    s = unicodedata.normalize("NFC", s or "")
    for k, v in QUOTE_MAP.items():
        s = s.replace(k, v)
    s = s.replace("\u00ad", "")
    s = re.sub(r"-\s*\n\s*", "", s)
    return re.sub(r"\s+", " ", s).strip()


def levenshtein(a, b):
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (0 if ca == b[j - 1] else 1))
        prev = cur
    return prev[lb]


def cer(gt, ocr):
    g, o = normalize(gt), normalize(ocr)
    return (0.0 if not o else 1.0) if not g else levenshtein(g, o) / len(g)


def wer(gt, ocr):
    gw = normalize(gt).split(" ") if normalize(gt) else []
    ow = normalize(ocr).split(" ") if normalize(ocr) else []
    return (0.0 if not ow else 1.0) if not gw else levenshtein(gw, ow) / len(gw)


def content_score(gt, ocr):
    gw = normalize(gt).split(" ") if normalize(gt) else []
    ow = normalize(ocr).split(" ") if normalize(ocr) else []
    cg, co = collections.Counter(gw), collections.Counter(ow)
    tp = sum((cg & co).values())
    p = tp / sum(co.values()) if co else 0.0
    r = tp / sum(cg.values()) if cg else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def stats(vals):
    if not vals:
        return {"n": 0}
    sv = sorted(vals)
    n = len(sv)

    def pct(p):
        return sv[max(0, min(n - 1, int(round(p / 100.0 * (n - 1)))))]

    return {
        "n": n, "mean": round(statistics.mean(sv), 4),
        "median": round(statistics.median(sv), 4),
        "p25": round(pct(25), 4), "p75": round(pct(75), 4),
        "min": round(sv[0], 4), "max": round(sv[-1], 4),
    }


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - m) / d, 4), round((c + m) / d, 4)]


def boot_median_ci(vals, iters=5000, seed=12345):
    if not vals:
        return [None, None]
    rng = random.Random(seed)
    n = len(vals)
    meds = sorted(statistics.median([vals[rng.randrange(n)] for _ in range(n)])
                  for _ in range(iters))
    lo = meds[int(0.025 * (iters - 1))]
    hi = meds[int(0.975 * (iters - 1))]
    return [round(lo, 4), round(hi, 4)]


def agg(rows):
    """Aggregate a list of per-variant dict rows into a condition summary.

    Mirrors the harness `agg()` exactly. Expects keys: cer, wer, doc_failure,
    empty_failure, silent_failure, exact, near_exact, delta_cer, content_f1,
    kind.
    """
    cers = [r["cer"] for r in rows]
    n = len(rows)
    fails = sum(r["doc_failure"] for r in rows)
    empt = sum(r["empty_failure"] for r in rows)
    sil = sum(r["silent_failure"] for r in rows)
    out = stats(cers)
    out.update({
        "wer_median": round(statistics.median([r["wer"] for r in rows]), 4) if rows else None,
        "exact": sum(r["exact"] for r in rows),
        "near_exact": sum(r["near_exact"] for r in rows),
        "failures": fails, "failure_rate": round(fails / n, 4) if n else None,
        "failure_rate_ci95": wilson(fails, n),
        "empty_failures": empt, "empty_failure_rate": round(empt / n, 4) if n else None,
        "empty_failure_rate_ci95": wilson(empt, n),
        "silent_failures": sil, "silent_failure_rate": round(sil / n, 4) if n else None,
        "silent_failure_rate_ci95": wilson(sil, n),
    })
    deltas = [r["delta_cer"] for r in rows if r["delta_cer"] is not None]
    if deltas:
        out["median_paired_delta_cer"] = round(statistics.median(deltas), 4)
        out["median_paired_delta_cer_ci95_bootstrap"] = boot_median_ci(deltas)
    f1s = [r["content_f1"] for r in rows if r["kind"] in STRUCTURED]
    if f1s:
        out["content_f1_median"] = round(statistics.median(f1s), 4)
        out["reading_order_gap_median"] = round(statistics.median(
            [(1 - r["cer"]) for r in rows if r["kind"] in STRUCTURED]), 4)
    return out
