#!/usr/bin/env python3
"""
Compute statistics on ads from -source, and on the subset of those
whose domain is also present in -ref.

Usage:
    python ad_stats.py -source source.csv -ref ref.csv

Prints a CSV to stdout with one row per category:
    category,rows,total_advertiser_total,mean_advertiser_total,share_of_rows,share_of_total
"""

import argparse
import csv
import sys
from urllib.parse import urlparse


def extract_domain(value: str) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "//" in value:
        host = urlparse(value).hostname or ""
    else:
        host = value.split("/", 1)[0]
        host = host.split("?", 1)[0]
        host = host.split("#", 1)[0]
        host = host.split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def load_ref_domains(path: str) -> set:
    domains = set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if not row:
                continue
            val = (row[1] if len(row) > 1 else row[0]).strip().lower()
            if not val or val in {"domain", "url", "host", "hostname"}:
                continue
            if val.startswith("www."):
                val = val[4:]
            domains.add(val)
    return domains


def to_number(value) -> float:
    """Best-effort numeric parse; returns 0.0 for blank/unparseable values."""
    if value is None:
        return 0.0
    s = str(value).strip().replace(",", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def summarize(rows, total_rows_hint=None):
    """Return (rows, total, mean, share_rows, share_total) for a list of (url, value)."""
    n = len(rows)
    total = sum(v for _, v in rows)
    mean = (total / n) if n else 0.0
    return n, total, mean


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Statistics on source ads vs. source∩ref ads."
    )
    parser.add_argument("-source", required=True, help="Path to source CSV")
    parser.add_argument("-ref", required=True, help="Path to reference CSV")
    args = parser.parse_args()

    ref_domains = load_ref_domains(args.ref)

    source_rows = []      # (domain, advertiser_total) for all source rows
    matched_rows = []     # subset whose domain is in ref
    unmatched_rows = []   # subset whose domain is NOT in ref

    with open(args.source, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = extract_domain(row.get("url", ""))
            value = to_number(row.get("advertiser_total"))
            source_rows.append((domain, value))
            if domain in ref_domains:
                matched_rows.append((domain, value))
            else:
                unmatched_rows.append((domain, value))

    # Totals used for share computation
    total_rows = len(source_rows)
    total_value = sum(v for _, v in source_rows)

    def stats(rows):
        n = len(rows)
        t = sum(v for _, v in rows)
        m = (t / n) if n else 0.0
        share_rows = (n / total_rows) if total_rows else 0.0
        share_total = (t / total_value) if total_value else 0.0
        return n, t, m, share_rows, share_total

    categories = [
        ("source_all",      source_rows),
        ("source_in_ref",   matched_rows),
        ("source_not_in_ref", unmatched_rows),
    ]

    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow([
        "category", "rows", "total_advertiser_total",
        "mean_advertiser_total", "share_of_rows", "share_of_total",
    ])
    for name, rows in categories:
        n, t, m, sr, st = stats(rows)
        writer.writerow([
            name,
            n,
            f"{t:.2f}",
            f"{m:.2f}",
            f"{sr:.4f}",
            f"{st:.4f}",
        ])


if __name__ == "__main__":
    main()