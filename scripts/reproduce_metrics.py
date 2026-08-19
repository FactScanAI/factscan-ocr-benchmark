#!/usr/bin/env python3
"""Reproduce every published study aggregate from data/per-variant.csv.

Zero credentials required. Reads only the published CSV/JSON files in `data/`.
Recomputes: condition-aggregates (overall + by_lang + by_kind),
failure-mode-aggregates, baseline-gate, outliers, paired-deltas, and the
per-condition totals. Exits non-zero if any recomputed value diverges from the
canonical JSON by more than the floating-point tolerance (1e-4).

Usage:
    python3 scripts/reproduce_metrics.py [--data DATA_DIR] [--quiet]
"""
import argparse
import collections
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics import CONDITIONS, STRUCTURED, agg, wilson, FAILURE_CER  # noqa: E402

TOL = 1e-4
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(os.path.dirname(HERE), "data")

FAIL = 0


def fail(msg):
    global FAIL
    FAIL += 1
    print("  MISMATCH:", msg, file=sys.stderr)


def approx_equal(a, b, path):
    """Compare numbers/strings/None within tolerance, recursing into lists/dicts."""
    if a is None or b is None:
        if a is not b:
            fail(f"{path}: None mismatch ({a!r} vs {b!r})")
        return
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if abs(float(a) - float(b)) > TOL:
            fail(f"{path}: {a} vs {b}")
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            fail(f"{path}: len {len(a)} vs {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            approx_equal(x, y, f"{path}[{i}]")
        return
    if isinstance(a, dict) and isinstance(b, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            fail(f"{path}: keys {ka ^ kb}")
        for k in a.keys() & b.keys():
            approx_equal(a[k], b[k], f"{path}.{k}")
        return
    if a != b:
        fail(f"{path}: {a!r} vs {b!r}")


def load_rows(data_dir):
    with open(os.path.join(data_dir, "per-variant.csv"), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def coerce(rows):
    """Cast CSV string columns to the typed values used by metrics.agg().

    Empty cells become None for every numeric column, matching the null values
    in the canonical JSON (e.g. rel_scale is null for blur-only rows).
    """
    float_cols = {"cer", "wer", "delta_cer", "content_precision", "content_recall",
                  "content_f1", "blur_radius_px", "rel_scale", "sharpness_varlap",
                  "sharpness_ratio"}
    int_cols = {"exact", "near_exact", "empty_failure", "silent_failure",
                "doc_failure", "gt_chars", "ocr_chars", "short_side_px",
                "long_side_px", "total_px", "out_w", "out_h"}
    out = []
    for r in rows:
        d = dict(r)
        for k in int_cols:
            v = d.get(k)
            d[k] = int(v) if v not in (None, "") else None
        for k in float_cols:
            v = d.get(k)
            d[k] = float(v) if v not in (None, "") else None
        if d.get("delta_cer") == "":
            d["delta_cer"] = None
        out.append(d)
    return out


def recompute(rows):
    by_cond = collections.defaultdict(list)
    for r in rows:
        by_cond[r["condition"]].append(r)

    overall = {c: agg(by_cond[c]) for c in CONDITIONS if by_cond[c]}
    by_lang, by_kind = {}, {}
    for c in CONDITIONS:
        if not by_cond[c]:
            continue
        by_lang[c] = {lg: agg([r for r in by_cond[c] if r["lang"] == lg])
                     for lg in ("en", "cs")}
        by_kind[c] = {k: agg([r for r in by_cond[c] if r["kind"] == k])
                      for k in ("prose", "table", "invoice", "mixed")}

    # failure-mode composition
    fm = {}
    for c in CONDITIONS:
        rs = by_cond[c]
        if not rs:
            continue
        n = len(rs)
        e = sum(r["empty_failure"] for r in rs)
        s = sum(r["silent_failure"] for r in rs)
        fm[c] = {"n": n, "success": n - e - s, "silent_nonempty_failure": s,
                 "empty_failure": e,
                 "empty_share_of_failures": round(e / (e + s), 4) if (e + s) else None,
                 "silent_share_of_failures": round(s / (e + s), 4) if (e + s) else None}

    # baseline gate
    import statistics
    brows = by_cond["baseline"]
    bad = []
    for r in sorted(brows, key=lambda r: -r["cer"]):
        if r["cer"] > FAILURE_CER:
            if r["empty_failure"]:
                cause = "empty OCR"
            elif r["content_f1"] >= 0.85:
                cause = "reading-order artifact (content F1 >= 0.85)"
            elif r["content_recall"] >= 0.85:
                cause = "reading-order artifact with insertions"
            elif r["content_recall"] < 0.6:
                cause = "recognition loss"
            else:
                cause = "unexplained"
            bad.append({"doc_id": r["doc_id"], "kind": r["kind"], "lang": r["lang"],
                        "cer": r["cer"], "content_f1": r["content_f1"],
                        "content_recall": r["content_recall"], "cause": cause})
    gate = {"summary": agg(brows), "failures_over_0_30": bad,
            "structured_content_f1_median": round(statistics.median(
                [r["content_f1"] for r in brows if r["kind"] in STRUCTURED]), 4)}

    # outliers: 5 worst per dimension
    def worst(dim):
        rs = [r for r in rows if r["dimension"] == dim]
        return [{k: r[k] for k in ("doc_id", "kind", "lang", "condition", "cer",
                                   "content_f1", "empty_failure", "silent_failure",
                                   "sharpness_ratio", "rel_scale")}
                for r in sorted(rs, key=lambda r: -r["cer"])[:5]]
    outliers = {"baseline": worst("baseline"), "blur": worst("blur"), "res": worst("res")}

    # paired-deltas
    paired = {}
    for did in sorted({r["doc_id"] for r in rows}):
        dr = {r["condition"]: r for r in rows if r["doc_id"] == did}
        row = [did]
        if dr:
            r0 = dr.get("baseline")
            base = r0["cer"] if r0 else None
            row = [did, dr[list(dr)[0]]["kind"], dr[list(dr)[0]]["lang"], base]
            for c in CONDITIONS[1:]:
                row.append(dr[c]["delta_cer"] if c in dr else "")
        paired[did] = row

    return {
        "condition_aggregates": {"overall": overall, "by_lang": by_lang, "by_kind": by_kind},
        "failure_modes": fm,
        "baseline_gate": gate,
        "outliers": outliers,
        "paired_deltas": paired,
    }


def verify(recomp, data_dir, quiet):
    print("== Reproducing FactScan OCR Benchmark aggregates ==")
    ca_pub = json.load(open(os.path.join(data_dir, "condition-aggregates.json")))
    fm_pub = json.load(open(os.path.join(data_dir, "failure-modes.json")))
    bg_pub = json.load(open(os.path.join(data_dir, "baseline-gate.json")))
    ol_pub = json.load(open(os.path.join(data_dir, "outliers.json")))

    print("[1/4] condition-aggregates.json ...")
    approx_equal(recomp["condition_aggregates"], ca_pub, "condition-aggregates")
    print("[2/4] failure-modes.json ...")
    approx_equal(recomp["failure_modes"], fm_pub, "failure-modes")
    print("[3/4] baseline-gate.json ...")
    approx_equal(recomp["baseline_gate"], bg_pub, "baseline-gate")
    print("[4/4] outliers.json ...")
    approx_equal(recomp["outliers"], ol_pub, "outliers")

    # paired-deltas CSV round-trip
    print("[extra] paired-deltas.csv round-trip ...")
    with open(os.path.join(data_dir, "paired-deltas.csv"), newline="", encoding="utf-8") as fh:
        pub_csv = list(csv.reader(fh))
    hdr = pub_csv[0]
    mism = 0
    for i, did in enumerate(sorted(recomp["paired_deltas"])):
        rec = pub_csv[i + 1]
        row = recomp["paired_deltas"][did]
        if rec[0] != rec[0] or rec[0] != did:
            pass
        # compare numeric cells
        for j in range(3, len(hdr)):
            pub_v = rec[j] if j < len(rec) else ""
            comp_v = row[j] if j < len(row) else ""
            if pub_v in ("", None) and comp_v in ("", None):
                continue
            try:
                if abs(float(pub_v) - float(comp_v)) > TOL:
                    mism += 1
            except (ValueError, TypeError):
                if pub_v != comp_v:
                    mism += 1
    if mism:
        fail(f"paired-deltas.csv: {mism} cell mismatch(es)")

    # headline counts from summary.json
    print("[extra] summary.json headline counts ...")
    summary = json.load(open(os.path.join(data_dir, "summary.json")))
    rows = load_rows(data_dir)
    typed = coerce(rows)
    assert len(typed) == summary["scope"]["ocr_executions"], "variant count mismatch"
    docs = {r["doc_id"] for r in typed}
    assert len(docs) == summary["scope"]["documents"], "document count mismatch"

    if FAIL:
        print(f"\nRESULT: FAIL — {FAIL} mismatch(es)", file=sys.stderr)
        return 1
    print("\nRESULT: PASS — all recomputed aggregates match the published JSON within 1e-4.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    rows = coerce(load_rows(args.data))
    recomp = recompute(rows)
    rc = verify(recomp, args.data, args.quiet)
    sys.exit(rc)


if __name__ == "__main__":
    main()
