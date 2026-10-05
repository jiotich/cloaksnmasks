#!/usr/bin/env python3
"""
Filter rows from -source based on whether their domain appears in -ref.

Usage:
    python filter_domains.py -source source.csv -ref ref.csv [-match|--match]
    python filter_domains.py -source source.csv -ref ref.csv [-no-match|--no-match]

By default, prints rows whose domain IS found in ref (same as before).
Use -no-match to instead print rows whose domain is NOT found in ref.
"""

import argparse
import csv
import sys
from urllib.parse import urlparse


def extract_domain(value: str) -> str:
    """Return a normalized hostname from a URL or plain domain string."""
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
    """Load the set of domains from the ref CSV (2nd column, or 1st if single-col)."""
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print source rows filtered by domain presence in ref."
    )
    parser.add_argument("-source", required=True, help="Path to source CSV")
    parser.add_argument("-ref", required=True, help="Path to reference CSV")

    # Mutually exclusive: pick exactly one (defaults to --match if neither given).
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-match", "--match",
        dest="mode",
        action="store_const",
        const="match",
        help="Output rows whose domain IS in ref (default).",
    )
    group.add_argument(
        "-no-match", "--no-match",
        dest="mode",
        action="store_const",
        const="no-match",
        help="Output rows whose domain is NOT in ref.",
    )
    parser.set_defaults(mode="match")

    args = parser.parse_args()

    ref_domains = load_ref_domains(args.ref)
    want_match = args.mode == "match"

    with open(args.source, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        writer = csv.writer(sys.stdout, lineterminator="\n")
        writer.writerow(fieldnames)

        for row in reader:
            domain = extract_domain(row.get("url", ""))
            in_ref = domain in ref_domains
            if in_ref == want_match:
                writer.writerow([row.get(fn, "") for fn in fieldnames])


if __name__ == "__main__":
    main()