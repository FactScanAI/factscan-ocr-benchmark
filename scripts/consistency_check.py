#!/usr/bin/env python3
"""Numerical consistency gate: every headline figure in README.md must trace
back to a value in the canonical JSON/CSV data files.

Parses README.md for fenced numeric tokens inside backtick-quoted spans and
table cells, then checks each against the published aggregates. Exits
non-zero if any cited number cannot be located in the source data within a
1e-4 tolerance (for floats) or exact match (for ints/strings).

Usage:
    python3 scripts/consistency_check.py [--data DATA_DIR] [--readme PATH]
"""
import argparse
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_DATA = os.path.join(REPO, "data")
DEFAULT_README = os.path.join(REPO, "README.md")
TOL = 1e-4
FAIL = 0

# Numbers we assert are NOT in the data (negated / derived), so they are
# whitelisted and not flagged as untraceable. These are ratios/deltas computed
# in prose from two cited values.
WHITELIST_NUMBERS = set()


def load_all_numbers(data_dir):
    """Collect every numeric token present in the canonical data files."""
    nums = set()
    for fn in os.listdir(data_dir):
        path = os.path.join(data_dir, fn)
        text = open(path, encoding="utf-8").read()
        # strip JSON keys so we only grab values
        for m in re.finditer(r"-?\d+\.?\d*(?:e-?\d+)?", text):
            tok = m.group(0)
            nums.add(tok)
    return nums


def extract_cited_numbers(readme_text):
    """Extract numbers that appear inside backtick spans or table cells.

    Fenced code blocks (```...```) are stripped first so that structural
    tree diagrams, citation blocks, and command examples are not mistaken for
    data citations. A number is considered "cited" if it sits between
    backticks or in a pipe-delimited table row. Bare prose numbers are loose
    and excluded.
    """
    # Strip fenced code blocks entirely (they are structural, not data).
    readme_text = re.sub(r"```.*?```", "", readme_text, flags=re.DOTALL)
    cited = []
    # backtick spans (inline code)
    for m in re.finditer(r"`([^`]*\d[^`]*)`", readme_text):
        for nm in re.finditer(r"-?\d+\.?\d*(?:e-?\d+)?", m.group(1)):
            cited.append((nm.group(0), m.group(1)))
    # table cells: content between pipes on lines starting with |
    for line in readme_text.splitlines():
        if line.strip().startswith("|") and "---" not in line:
            for cell in line.split("|"):
                for nm in re.finditer(r"-?\d+\.?\d*(?:e-?\d+)?", cell):
                    cited.append((nm.group(0), cell.strip()))
    return cited


def main():
    global FAIL
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--readme", default=DEFAULT_README)
    args = ap.parse_args()

    readme_text = open(args.readme, encoding="utf-8").read()
    data_nums = load_all_numbers(args.data)
    cited = extract_cited_numbers(readme_text)

    print("== README numerical consistency gate ==")
    print(f"  cited numbers: {len(cited)}  |  data tokens: {len(data_nums)}")

    for tok, ctx in cited:
        # normalize float forms (0.0 vs 0) for matching
        try:
            val = float(tok)
            matches = any(abs(val - float(d)) <= TOL for d in data_nums
                          if _safe_float(d))
        except ValueError:
            matches = tok in data_nums
        if not matches and tok not in WHITELIST_NUMBERS:
            FAIL += 1
            print(f"  UNTRACEABLE: {tok!r}  context: {ctx!r}", file=sys.stderr)

    if FAIL:
        print(f"\nRESULT: FAIL — {FAIL} untraceable cited number(s)", file=sys.stderr)
        return 1
    print("\nRESULT: PASS — every cited number traces to the canonical data.")
    return 0


def _safe_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    sys.exit(main())
