#!/usr/bin/env python3
"""
Stacked bar chart of TLD share across advertiser-count strata, showing both
advertiser-weighted and domain-counted bars side by side, with an optional
isolated reference group for a filtered CSV.

The first stratum ("1") draws a single bar, since advertiser-weighted and
domain-counted views are identical there (every domain has exactly one
advertiser). Every other stratum draws a pair of bars (adv | dom). Both
views are normalized to 100% per bar.

Strata (based on `advertiser_total`):
    1 (singular) | 2-10 | 11-100 | 101-1000 | >1000

Usage:
    python tld_strata.py domains.csv
    python tld_strata.py domains.csv -ref selected.csv
    python tld_strata.py domains.csv -ref selected.csv -o chart.png --top 20

Requirements:
    pip install matplotlib numpy
    pip install tldextract        # optional, but recommended (accurate public suffixes)
"""

import argparse
import csv
import sys
from collections import Counter, OrderedDict

import numpy as np
import matplotlib.pyplot as plt

try:  # optional dependency
    import tldextract

    _TLDEXTRACT = tldextract.TLDExtract(suffix_list_urls=())  # bundled snapshot, no network
except ImportError:  # pragma: no cover
    _TLDEXTRACT = None


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

STRATA = [
    ("1", 1, 1),
    ("2\u201310", 2, 10),
    ("11\u2013100", 11, 100),
    ("101\u20131000", 101, 1000),
    (">1000", 1001, float("inf")),
]

SECOND_LEVEL_LABELS = {
    "com", "co", "net", "org", "gov", "edu", "ac", "mil", "sch", "gen",
    "ind", "firm", "nom", "web", "info", "biz", "arts", "rec", "gob",
    "gouv", "med", "res", "or", "ne", "go", "in", "id", "lg",
}

PALETTE = [
    "#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00",
    "#56B4E9", "#F0E442", "#882255", "#44AA99", "#999933",
    "#9C755F", "#D4A6C8", "#8CD17D", "#FF9D9A", "#A0CBE8",
]
OTHER_COLOR = "#666666"
LABEL_MIN_PCT = 4.0

# Bar geometry
BAR_W = 0.36
BAR_OFFSET = 0.2   # half of (BAR_W + intra-pair gap)
BAR_EDGE = "white"

# Slots that draw a single (unpaired) bar. Index 0 is the singular stratum,
# where the advertiser-weighted and domain-counted views are identical.
SINGLE_BAR_SLOTS = {0}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def public_suffix(host: str) -> str:
    """Return the public suffix (e.g. 'com', 'com.br', 'co.uk') of a host string."""
    host = (host or "").strip().lower()
    if not host:
        return ""

    if "//" in host:
        host = host.split("//", 1)[1]
    host = host.split("/", 1)[0]
    host = host.split("?", 1)[0]
    host = host.split("#", 1)[0]
    host = host.split("@")[-1]
    host = host.split(":")[0]
    host = host.strip().strip(".")
    if not host:
        return ""

    if _TLDEXTRACT is not None:
        ext = _TLDEXTRACT(host)
        if ext.suffix:
            return ext.suffix
        return host.rsplit(".", 1)[-1]

    labels = host.split(".")
    if len(labels) == 1:
        return labels[0]
    if len(labels) >= 3 and labels[-2] in SECOND_LEVEL_LABELS:
        return ".".join(labels[-2:])
    return labels[-1]


def classify(total: int) -> str:
    if total <= 1:
        return STRATA[0][0]
    for label, lo, hi in STRATA:
        if lo <= total <= hi:
            return label
    return STRATA[-1][0]


def load_csv(path: str):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh, skipinitialspace=True)
        try:
            header = [h.strip().lower() for h in next(reader)]
        except StopIteration:
            return rows

        url_i = header.index("url") if "url" in header else 0
        tot_i = header.index("advertiser_total") if "advertiser_total" in header else 1
        needed = max(url_i, tot_i)

        for row in reader:
            if len(row) <= needed:
                continue
            url = row[url_i].strip()
            if not url:
                continue
            raw_total = row[tot_i].strip().replace(",", "")
            try:
                total = int(float(raw_total))
            except ValueError:
                continue
            rows.append((url, total))
    return rows


def build_counts(rows, count_domains: bool = False):
    counts = OrderedDict((label, Counter()) for label, _, _ in STRATA)
    for url, total in rows:
        label = classify(total)
        tld = public_suffix(url)
        if tld:
            counts[label][tld] += 1 if count_domains else total
    return counts


def aggregate_all(counts) -> Counter:
    overall = Counter()
    for c in counts.values():
        overall.update(c)
    return overall


def _rel_luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    rgb = (int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _text_color(hex_color: str) -> str:
    lum = _rel_luminance(hex_color)
    dark = _rel_luminance("#333333")
    white_ratio = 1.05 / (lum + 0.05)
    dark_ratio = (lum + 0.05) / (dark + 0.05)
    return "#FFFFFF" if white_ratio >= dark_ratio else "#333333"


def _segment_label(cat: str, pct: float) -> str:
    """Two-line label: TLD on top, percentage below."""
    return f"{cat}\n{pct:.0f}%"


# --------------------------------------------------------------------------- #
# Plotting
# --------------------------------------------------------------------------- #

def make_chart(counts_main_adv, counts_main_dom,
               counts_ref_adv, counts_ref_dom,
               top_n: int, title: str):

    strata_labels = [label for label, _, _ in STRATA]

    slots = [(label, counts_main_adv[label], counts_main_dom[label])
             for label in strata_labels]
    if counts_ref_adv is not None:
        slots.append(("Tranco Top 1k",
                      aggregate_all(counts_ref_adv),
                      aggregate_all(counts_ref_dom)))

    n_slots = len(slots)
    slot_x = np.arange(n_slots, dtype=float)

    # Which slots get a single (unpaired) bar
    single_mask = np.array([si in SINGLE_BAR_SLOTS for si in range(n_slots)])
    pair_slots = np.where(~single_mask)[0]

    # x positions
    x_single = slot_x[single_mask]
    x_adv = slot_x[pair_slots] - BAR_OFFSET
    x_dom = slot_x[pair_slots] + BAR_OFFSET

    # Rank TLDs by combined weight across both modes and all slots
    overall = Counter()
    for _, ca, cd in slots:
        overall.update(ca)
        overall.update(cd)
    top_tlds = [tld for tld, _ in overall.most_common(top_n)]
    top_set = set(top_tlds)
    other_label = "other"
    categories = top_tlds + [other_label]
    n_cat = len(categories)

    colors = [PALETTE[i % len(PALETTE)] for i in range(n_cat)]
    colors[-1] = OTHER_COLOR

    adv_totals = np.array([sum(ca.values()) for _, ca, _ in slots], dtype=float)
    dom_totals = np.array([sum(cd.values()) for _, _, cd in slots], dtype=float)

    adv_pct = np.zeros((n_cat, n_slots), dtype=float)
    dom_pct = np.zeros((n_cat, n_slots), dtype=float)

    for ci, cat in enumerate(categories):
        for si, (_, ca, cd) in enumerate(slots):
            if cat == other_label:
                av = sum(v for k, v in ca.items() if k not in top_set)
                dv = sum(v for k, v in cd.items() if k not in top_set)
            else:
                av = ca.get(cat, 0)
                dv = cd.get(cat, 0)
            if adv_totals[si] > 0:
                adv_pct[ci, si] = av / adv_totals[si] * 100.0
            if dom_totals[si] > 0:
                dom_pct[ci, si] = dv / dom_totals[si] * 100.0

    adv_bottoms = np.vstack([np.zeros(n_slots),
                             np.cumsum(adv_pct, axis=0)[:-1]])
    dom_bottoms = np.vstack([np.zeros(n_slots),
                             np.cumsum(dom_pct, axis=0)[:-1]])

    fig, ax = plt.subplots(figsize=(15, 8.2))
    tld_handles = {}

    for ci, (cat, color) in enumerate(zip(categories, colors)):
        # ---- Paired bars (every slot except the single-bar ones) --------- #
        if len(pair_slots) > 0:
            bars_adv = ax.bar(
                x_adv, adv_pct[ci, pair_slots], BAR_W,
                bottom=adv_bottoms[ci, pair_slots],
                color=color, edgecolor=BAR_EDGE, linewidth=0.7,
                zorder=2,
            )
            ax.bar(
                x_dom, dom_pct[ci, pair_slots], BAR_W,
                bottom=dom_bottoms[ci, pair_slots],
                color=color, edgecolor=BAR_EDGE, linewidth=0.7,
                zorder=2,
            )
        else:
            bars_adv = None

        # ---- Single centered bar for slot 0 ------------------------------ #
        bars_single = ax.bar(
            x_single, adv_pct[ci, single_mask], BAR_W,
            bottom=adv_bottoms[ci, single_mask],
            color=color, edgecolor=BAR_EDGE, linewidth=0.7,
            zorder=2,
        )

        # Pick a representative handle for the TLD legend
        if cat not in tld_handles:
            tld_handles[cat] = (bars_single[0] if len(bars_single) > 0
                                else bars_adv[0])

    # ---- Percentage + TLD annotations ------------------------------------ #
    for si in range(n_slots):
        if si in SINGLE_BAR_SLOTS:
            xs = [slot_x[si]]
            bottoms_list = [adv_bottoms]
            pcts_list = [adv_pct]
        else:
            xs = [x_adv[np.where(pair_slots == si)[0][0]],
                  x_dom[np.where(pair_slots == si)[0][0]]]
            bottoms_list = [adv_bottoms, dom_bottoms]
            pcts_list = [adv_pct, dom_pct]

        for x_pos, bottoms, pcts in zip(xs, bottoms_list, pcts_list):
            for ci in range(n_cat):
                p = pcts[ci, si]
                if p >= LABEL_MIN_PCT:
                    ax.text(
                        x_pos, bottoms[ci, si] + p / 2.0,
                        _segment_label(categories[ci], p),
                        ha="center", va="center",
                        fontsize=7.5, fontweight="bold",
                        color=_text_color(colors[ci]), zorder=3,
                    )

    # ---- n= labels above each bar ---------------------------------------- #
    for si in range(n_slots):
        if si in SINGLE_BAR_SLOTS:
            if adv_totals[si] > 0:
                ax.text(slot_x[si], 101.2, f"n={int(adv_totals[si]):,}",
                        ha="center", va="bottom", fontsize=7, color="#555555")
        else:
            if adv_totals[si] > 0:
                ax.text(x_adv[np.where(pair_slots == si)[0][0]], 101.2,
                        f"n={int(adv_totals[si]):,}",
                        ha="center", va="bottom", fontsize=7, color="#555555")
            if dom_totals[si] > 0:
                ax.text(x_dom[np.where(pair_slots == si)[0][0]], 101.2,
                        f"n={int(dom_totals[si]):,}",
                        ha="center", va="bottom", fontsize=7, color="#555555")

    # ---- Axes / decoration ----------------------------------------------- #
    ax.set_xticks(slot_x)
    ax.set_xticklabels([label for label, _, _ in slots], fontsize=11)
    ax.set_xlim(-0.6, n_slots - 0.4)
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 10))
    ax.set_xlabel("Advertisers per domain", fontsize=11, labelpad=10)
    ax.set_ylabel("Share (%)", fontsize=11, labelpad=10)
    ax.grid(axis="y", linestyle=":", alpha=0.35, color="#999999")
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#BBBBBB")

    if counts_ref_adv is not None:
        ax.axvline(n_slots - 1 - 0.5, color="#999999",
                   linestyle="--", linewidth=1, alpha=0.6, zorder=1)

    # ---- TLD legend (top, horizontal) ------------------------------------ #
    ax.legend(
        handles=list(tld_handles.values()),
        labels=list(tld_handles.keys()),
        loc="lower center", bbox_to_anchor=(0.5, 1.04),
        frameon=False, fontsize=12,
        ncol=n_cat,
        columnspacing=0.8, handlelength=1.2,
        handletextpad=0.4, labelspacing=0.4,
        borderaxespad=0.0,
    )

    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=("Stacked bar chart of TLD share per advertiser-count stratum, "
                     "showing both advertiser-weighted and domain-counted bars."),
    )
    parser.add_argument("csv", help="CSV file with columns: url, advertiser_total")
    parser.add_argument("-ref", "--reference", metavar="CSV", default=None,
                        help="optional second CSV (same format), shown as an isolated reference group")
    parser.add_argument("-o", "--output", metavar="PATH", default=None,
                        help="save the chart to PATH instead of displaying it")
    parser.add_argument("--top", type=int, default=15,
                        help="number of TLDs shown individually; the rest become 'other' (default: 15)")
    parser.add_argument("--title", default=None,
                        help="chart title (default: 'TLD share by stratum — advertisers vs. domains')")
    args = parser.parse_args(argv)

    title = args.title or "TLD share by stratum \u2014 advertisers vs. domains"

    main_rows = load_csv(args.csv)
    if not main_rows:
        print(f"warning: no usable rows found in {args.csv}", file=sys.stderr)
    counts_main_adv = build_counts(main_rows, count_domains=False)
    counts_main_dom = build_counts(main_rows, count_domains=True)

    counts_ref_adv = None
    counts_ref_dom = None
    if args.reference:
        ref_rows = load_csv(args.reference)
        if not ref_rows:
            print(f"warning: no usable rows found in {args.reference}", file=sys.stderr)
        counts_ref_adv = build_counts(ref_rows, count_domains=False)
        counts_ref_dom = build_counts(ref_rows, count_domains=True)

    fig = make_chart(counts_main_adv, counts_main_dom,
                     counts_ref_adv, counts_ref_dom,
                     args.top, title)

    if args.output:
        fig.savefig(args.output, dpi=150, bbox_inches="tight")
        print(f"saved chart to {args.output}")
    else:
        plt.show()

    return 0


if __name__ == "__main__":
    sys.exit(main())