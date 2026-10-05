"""Deceptive-pattern analysis for a dataset of adverts.

Adverts (Meta Ad Library rows stored in a SQLite database) embed target URLs
in their snapshots; separate HTTP probes resolved where those URLs actually
lead.  This module bundles:

* a small SQLite / JSON utility layer for the advert database,
* detectors for the deceptive patterns
    - ``card_cloaking``    cards of one ad pointing at several eTLD+1s,
    - ``url_masking``      displayed caption domain != link target domain,
    - ``single_redirect``  link domain with one stable redirect target,
    - ``multi_redirect``   link domain resolving to several final domains,
* :func:`scan_ads` -- a streaming single pass over the advert table producing
  four data frames (inventory / deceit / masks / pairs), and
* report functions printing headline statistics and drawing the plots.

As a script it runs the full pipeline end to end::

    python ad_deception.py [--db PATH] [--redir-dir PATH] [--persist] [--smoke]

Everything is importable without side effects; see ``main`` for the intended
orchestration.
"""

import argparse
import json
import random
import sqlite3
from itertools import islice
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import tldextract

__all__ = [
    "DB_PATH", "REDIR_RESULTS_DIR", "DECEIT_TYPES", "META_URLS",
    "DISPLAY_FORMATS", "CARD_FORMATS", "SAMPLE_AD_IDS",
    "registered_domain",
    "get_db_connection", "query", "get_ad_data", "get_ad_ids",
    "count_display_formats",
    "sort_dict", "get_display_format", "get_dir_files", "get_sample",
    "plot_bar_chart", "plot_ctas",
    "extract_url_caption_pairs", "is_url_masked", "card_domains",
    "is_card_cloaked", "load_redirection_results", "classify_redirections",
    "scan_ads", "save_parquet", "smoke_test_displays",
    "report_deception_stats", "report_owner_analysis", "report_url_masking",
    "report_card_cloaking", "report_redirection_cloaking", "main",
]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DECEIT_TYPES = ["card_cloaking", "multi_redirect", "single_redirect", "url_masking"]
META_URLS = {"fb.me", "fb.com", "wa.me"}

DISPLAY_FORMATS = {  # display_format -> structural family
    "DCO": "cards", "DPA": "cards", "CAROUSEL": "cards",
    "MULTI_IMAGES": "multi", "MULTI_VIDEOS": "multi", "MULTI_MEDIAS": "multi",
    "PAGE_LIKE": "single", "IMAGE": "single", "VIDEO": "single",
    "EVENT": "single", "TEXT": "single", "error": "error",
}
CARD_FORMATS = {fmt for fmt, struct in DISPLAY_FORMATS.items() if struct == "cards"}

SAMPLE_AD_IDS = {  # one known ad per format, for smoke-testing the extractors
    "DCO": "944642594838490", "DPA": "2228284641292272", "CAROUSEL": "2025602804654035",
    "MULTI_IMAGES": "949928980957538", "MULTI_VIDEOS": "1985371835395094",
    "MULTI_MEDIAS": "990722980042041", "PAGE_LIKE": "940429358839765",
    "IMAGE": "966377712513671", "VIDEO": "2448276192267565",
    "EVENT": "898428686557991", "TEXT": "925699990329230", "error": "error",
}

# Paths are relative to the original notebook's location; override with
# --db / --redir-dir when running as a script.
DB_PATH = Path("../../full_lighsnap.db")
REDIR_RESULTS_DIR = Path("../data/redirection_results")

# ---------------------------------------------------------------------------
# TLD extraction
# ---------------------------------------------------------------------------

# Single shared extractor.  include_psl_private_domains=True makes the PSL's
# private entries (blogspot.com, github.io, ...) count as suffixes, so e.g.
# "foo.blogspot.com" yields "foo.blogspot.com" rather than "blogspot.com".
# All domain extraction in this module must go through registered_domain().
_TLD_EXTRACT = tldextract.TLDExtract(include_psl_private_domains=True)


def registered_domain(url):
    """Lowercased eTLD+1 of `url`; '' if absent/unparseable."""
    if not url:
        return ""
    return _TLD_EXTRACT(url).top_domain_under_registry_suffix.lower()


# ---------------------------------------------------------------------------
# Utils: dicts / files / sampling / plotting
# ---------------------------------------------------------------------------

def sort_dict(data, reverse=True):
    """dict or pandas Series -> [(key, value)] sorted by value."""
    return sorted(dict(data).items(), key=lambda kv: kv[1], reverse=reverse)


def get_display_format(ad_data, default="error"):
    return (ad_data.get("snapshot") or {}).get("display_format", default)


def get_dir_files(path, extension=""):
    path = Path(path)
    if not path.is_dir():
        return []
    return [p for p in path.glob(f"*{extension}" if extension else "*") if p.is_file()]


def get_sample(population, n):
    population = list(population)
    if n > len(population):
        raise ValueError("Sample larger than population.")
    return random.sample(population, n)


def plot_bar_chart(data, ylog=False, label_fmt="%.2f", title="", figsize=(8, 6)):
    """Bar plot of `data` (dict or Series of category -> value); returns (fig, ax)."""
    items = sort_dict(data)
    if not items:
        print(f"[{title}] nothing to plot.")
        return None, None
    categories, values = zip(*items)
    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.bar(categories, values, color="skyblue", edgecolor="black")
    ax.bar_label(bars, fmt=label_fmt, padding=3)
    if ylog:
        ax.set_yscale("log")
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=45, ha="right")
    ax.set_title(title)
    plt.tight_layout()
    plt.show()
    return fig, ax


def plot_ctas(inventory_df, ad_ids, threshold=100, title="CTAs"):
    """CTA-type mix for `ad_ids`, cutting off CTAs used at most `threshold` times."""
    sub = inventory_df[inventory_df["ad_id"].isin(set(ad_ids))]
    print(f"advertisers:  {sub['owner_id'].nunique()}")
    counts = sub["cta_type"].dropna().value_counts()
    plot_bar_chart(counts[counts > threshold], label_fmt="%g", title=title)


# ---------------------------------------------------------------------------
# SQL operations
# ---------------------------------------------------------------------------

def get_db_connection(db_path: Path = DB_PATH):
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")
    return sqlite3.connect(db_path)


def query(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.Error as e:
        print(f"SQLite error ({sql.strip().splitlines()[0]}...): {e}")
        return []


def get_ad_data(conn, ad_id):
    row = query(conn, "SELECT metadata FROM advert WHERE ad_archive_id = ?", (ad_id,))
    if not row:
        print(f"No advert found with id {ad_id}.")
        return None
    return json.loads(row[0][0])


def get_ad_ids(conn, *, fmt=None, formats=None, owner_id=None):
    """Flexible id lookup; replaces get_carded_ad_ids/get_ids_by_fmt/get_ads_from_owner."""
    clauses, params = [], []
    if fmt is not None:
        clauses.append("display_format = ?")
        params.append(fmt)
    if formats is not None:
        clauses.append(f"display_format IN ({','.join('?' * len(formats))})")
        params.extend(formats)
    if owner_id is not None:
        clauses.append("advertiser_id = ?")
        params.append(owner_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return [r[0] for r in query(conn, f"SELECT ad_archive_id FROM advert{where}", params)]


def count_display_formats(conn, ad_ids=None, batch_size=500):
    """Counts by display_format; restricted to `ad_ids` (batched) if given."""
    if ad_ids is None:
        return dict(query(conn, "SELECT display_format, COUNT(*) FROM advert GROUP BY display_format"))
    counts, it = {}, iter(ad_ids)
    while batch := list(islice(it, batch_size)):
        placeholders = ",".join("?" * len(batch))
        rows = query(conn, f"""
            SELECT display_format, COUNT(*) FROM advert
            WHERE ad_archive_id IN ({placeholders})
            GROUP BY display_format""", batch)
        for fmt, n in rows:
            counts[fmt] = counts.get(fmt, 0) + n
    return counts


# ---------------------------------------------------------------------------
# Deceptive pattern detection: URL masking & card cloaking
# ---------------------------------------------------------------------------

def extract_url_caption_pairs(ad_data):
    """(link_url, caption) per displayed card; [] when absent or format unknown."""
    snapshot = ad_data.get("snapshot") or {}
    structure = DISPLAY_FORMATS.get(snapshot.get("display_format"))
    if structure in ("single", "multi"):
        return [(snapshot.get("link_url"), snapshot.get("caption"))]
    if structure == "cards":
        return [(c.get("link_url"), c.get("caption")) for c in (snapshot.get("cards") or [])]
    return []


def is_url_masked(url, caption):
    """True when the caption displays a domain other than the link's target."""
    d_url, d_cap = registered_domain(url), registered_domain(caption)
    if not d_url or not d_cap:
        return False  # unparseable -> treated like the old validator rejection
    return d_url != d_cap


def card_domains(snapshot):
    return {d for d in (registered_domain(c.get("link_url"))
                        for c in (snapshot.get("cards") or [])) if d}


def is_card_cloaked(snapshot):
    """True when the ad's cards point at more than one registered domain."""
    return len(card_domains(snapshot)) > 1


def smoke_test_displays(conn):
    """Print the extracted (link_url, caption) pairs for one known ad per format."""
    for fmt, ad_id in SAMPLE_AD_IDS.items():
        print(f"{fmt}: {extract_url_caption_pairs(get_ad_data(conn, ad_id))}")


# ---------------------------------------------------------------------------
# Deceptive pattern detection: conditional redirects
# ---------------------------------------------------------------------------

def load_redirection_results(path: Path = REDIR_RESULTS_DIR):
    """requested_domain -> {result_file_stem: [resolved domains], 'all': union}."""
    files = get_dir_files(path, ".json")
    if not files:
        print(f"No redirection result files under {path}.")
        return {}

    results = {}
    for file in files:
        with open(file, encoding="utf-8") as fh:
            content = json.load(fh)
        metadata = content.pop("metadata", {})
        if metadata.get("total") != len(content):
            print(f"Aborting: {file} declares {metadata.get('total')} domains, found {len(content)}.")
            return {}

        stem = Path(file).stem
        for requested, resolved_urls in content.items():
            resolved = {registered_domain(u) for u in resolved_urls if u != "errored out"}
            resolved.discard("")
            results.setdefault(registered_domain(requested), {})[stem] = sorted(resolved)

    for per_source in results.values():
        per_source["all"] = {d for ds in per_source.values() for d in ds}
    return results


def classify_redirections(results):
    """
    Bucket requested domains by observed resolution behaviour.
    Per domain d, with A = union of resolutions across all probe sources:
      dead   : |A| == 0               -> site down / all probes failed
                                        (a source with 0 responses among otherwise
                                         live domains -> re-probe that source)
      no     : |A| == 1, A == {d}     -> resolves to itself
      single : |A| == 1, A != {d}     -> stable redirect, one fixed final address
      multi  : |A| > 1                -> several final domains possible
                   - one resolution per source, differing across sources
                     (IP/geolocation-conditioned resolution)
                   - |A| < sum(per-source sizes) -> overlapping resolutions
                   - one source with N > 1, rest 1, |A| >= N+1 -> targeted at that source
    """
    strata = {"no": {}, "single": {}, "multi": {}, "dead": []}
    if not results:
        print("No redirection results to classify.")
        return strata
    for domain, per_source in results.items():
        finals = per_source["all"]
        if not finals:
            strata["dead"].append(domain)
        elif len(finals) == 1:
            key = "no" if next(iter(finals)) == domain else "single"
            strata[key][domain] = {k: sorted(v) for k, v in per_source.items()}
        else:
            strata["multi"][domain] = {k: sorted(v) for k, v in per_source.items()}

    total = sum(len(v) for v in strata.values())
    print(f"Integrity Test Success: {total == len(results)}")
    for k in ("dead", "no", "single", "multi"):
        print(f"{k:8s}| {len(strata[k]) / total:.2f} |")
    return strata


# ---------------------------------------------------------------------------
# Scan pipeline
# ---------------------------------------------------------------------------

def scan_ads(conn, ad_ids, single_redirect_domains, multi_redirect_domains):
    """
    Streaming single pass over advert.

    Returns:
      inventory_df : ad_id, owner_id, display_format, cta_type,
                     n_cards, card_n_domains       (card cols NaN for non-carded)
      deceit_df    : ad_id, owner_id, display_format, deceit_type
      masks_df     : ad_id, mask_domain, target_domain
      pairs_df     : ad_id, display_format, url_domain, caption_domain, is_masked
                     -- every parseable (link, caption) pair, masked or not;
                        the unmasked captions act as the lexical control group
    """
    inv, dec, msk, prs = [], [], [], []
    wanted = set(ad_ids)
    for ad_id, raw in conn.execute("SELECT ad_archive_id, metadata FROM advert"):
        if wanted and ad_id not in wanted:
            continue
        meta = json.loads(raw)
        snap = meta.get("snapshot") or {}
        fmt = snap.get("display_format", "error")
        owner = meta.get("page_id")
        structure = DISPLAY_FORMATS.get(fmt)
        cards = snap.get("cards") or []
        inv.append((ad_id, owner, fmt, snap.get("cta_type"),
                    len(cards) if structure == "cards" else None,
                    len(card_domains(snap)) if structure == "cards" else None))

        patterns = set()
        if structure == "cards" and is_card_cloaked(snap):
            patterns.add("card_cloaking")

        for url, caption in extract_url_caption_pairs(meta):
            udom, cdom = registered_domain(url), registered_domain(caption)
            if not udom:
                continue
            masked = bool(cdom) and udom != cdom  # same criterion as is_url_masked()
            prs.append((ad_id, owner, fmt, udom, cdom, masked))
            if masked:
                msk.append((ad_id, cdom, udom))
                patterns.add("url_masking")
            if udom in single_redirect_domains and udom not in META_URLS:
                patterns.add("single_redirect")
            elif udom in multi_redirect_domains:
                patterns.add("multi_redirect")

        # sorted() -> deterministic deceit_df row order (patterns is a set)
        dec.extend((ad_id, owner, fmt, p) for p in sorted(patterns))

    inventory_df = pd.DataFrame(inv, columns=["ad_id", "owner_id", "display_format",
                                              "cta_type", "n_cards", "card_n_domains"])
    deceit_df = pd.DataFrame(dec, columns=["ad_id", "owner_id", "display_format", "deceit_type"])
    masks_df = pd.DataFrame(msk, columns=["ad_id", "mask_domain", "target_domain"])
    pairs_df = pd.DataFrame(prs, columns=["ad_id", "owner", "display_format",
                                          "url_domain", "caption_domain", "is_masked"])
    return inventory_df, deceit_df, masks_df, pairs_df


def save_parquet(frames, out_dir=Path(".")):
    """Persist scan data frames as <name>.parquet (needs `pip install pyarrow`)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in frames.items():
        path = out_dir / f"{name}.parquet"
        df.to_parquet(path)
        print(f"saved {path}")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def report_deception_stats(inventory_df, deceit_df):
    """Deceptive-pattern totals, overall and broken down by display format."""
    total_ads = len(inventory_df)
    if not total_ads:
        print("No ads in inventory; nothing to report.")
        return
    deceptive_total = deceit_df["ad_id"].nunique()
    print(f"Total ads: {total_ads}")
    print(f"Total ads with deceptive patterns: {deceptive_total} ({100 * deceptive_total / total_ads:.1f}% of total)")

    ads_per_type = deceit_df.groupby("deceit_type")["ad_id"].nunique().reindex(DECEIT_TYPES, fill_value=0)
    for deceit_type, n in ads_per_type.items():
        print(f"\tads in {deceit_type} class: {n}")
    print()

    fmt_totals = inventory_df["display_format"].value_counts()
    fmt_deceptive = deceit_df.drop_duplicates("ad_id")["display_format"].value_counts()
    types_by_fmt = deceit_df.groupby(["display_format", "deceit_type"])["ad_id"].nunique()

    for fmt, n_dec in fmt_deceptive.items():
        total = int(fmt_totals[fmt])
        print(f"[{total} {fmt}]:\t {n_dec} deceptive ({100 * n_dec / total:.1f}%)")
        if fmt in types_by_fmt.index.get_level_values("display_format"):
            for deceit_type, n in types_by_fmt.xs(fmt, level="display_format").sort_values(ascending=False).items():
                print(f"\t{deceit_type}: {n} ({100 * n / total:.1f}%)")
        print()


def report_owner_analysis(deceit_df):
    """Advertiser overview; highlights owners combining >= 3 deceit types."""
    owners_per_type = deceit_df.groupby("deceit_type")["owner_id"].nunique().reindex(DECEIT_TYPES)
    print(owners_per_type, "\n")

    deceit_ads_per_owner = deceit_df.groupby("owner_id")["ad_id"].nunique().sort_values(ascending=False)

    top_owners = deceit_ads_per_owner.index
    top_owner_types = (deceit_df[deceit_df["owner_id"].isin(top_owners)]
                       .groupby("owner_id")["deceit_type"].value_counts())
    for owner, counts in top_owner_types.groupby(level=0):
        if len(counts) > 2:
            print(owner, dict(counts.droplevel(0)))


def report_url_masking(inventory_df, deceit_df, masks_df):
    """Mask usage/target spread, masking share per format, CTA mix vs. control."""
    fmt_totals = inventory_df["display_format"].value_counts()
    fmt_deceptive = deceit_df.drop_duplicates("ad_id")["display_format"].value_counts()

    mask_uses = masks_df.groupby("mask_domain").size()                         # times each mask is used
    mask_targets = masks_df.groupby("mask_domain")["target_domain"].nunique()  # distinct destinations per mask

    plot_bar_chart(mask_uses[mask_uses > 200], label_fmt="%g", title="masks (uses)")
    plot_bar_chart(mask_targets[mask_targets > 6], label_fmt="%g", title="masks (distinct targets)")

    um_masking_share = (100 * deceit_df[deceit_df["deceit_type"] == "url_masking"]
                        .groupby("display_format")["ad_id"].nunique()
                        / fmt_totals.reindex(fmt_deceptive.index)).dropna()
    plot_bar_chart(um_masking_share, title="url masking %")

    um_ids = deceit_df.loc[deceit_df["deceit_type"] == "url_masking", "ad_id"]
    innocent_ids = inventory_df.loc[~inventory_df["ad_id"].isin(deceit_df["ad_id"]), "ad_id"]
    plot_ctas(inventory_df, um_ids, 100, "url masking CTAs")
    plot_ctas(inventory_df, get_sample(innocent_ids, len(um_ids)), 100, "normal")


def report_card_cloaking(inventory_df, deceit_df):
    """Card-cloaking share per format; CTA mix vs. carded non-deceitful control."""
    fmt_totals = inventory_df["display_format"].value_counts()
    fmt_deceptive = deceit_df.drop_duplicates("ad_id")["display_format"].value_counts()

    card_ids = deceit_df.loc[deceit_df["deceit_type"] == "card_cloaking", "ad_id"]
    card_share = (100 * deceit_df[deceit_df["deceit_type"] == "card_cloaking"]
                  .groupby("display_format")["ad_id"].nunique()
                  / fmt_totals.reindex(fmt_deceptive.index)).dropna()
    plot_bar_chart(card_share, title="card cloaking")

    no_deceit_cards = inventory_df[(inventory_df["display_format"].isin(CARD_FORMATS))
                                   & ~inventory_df["ad_id"].isin(deceit_df["ad_id"])]["ad_id"]

    plot_ctas(inventory_df, card_ids, 10, "card cloaking CTAs")
    plot_ctas(inventory_df, get_sample(no_deceit_cards, len(card_ids)), 10, "carded non-deceitful CTAs")


def report_redirection_cloaking(inventory_df, deceit_df):
    """Redirect-domain share per format; CTA mix vs. innocent control.

    NOTE: the original notebook divided a *global* redirect count by each
    format's total; this divides each format's own redirect count.  Revert if
    the old behaviour was intended.
    """
    fmt_totals = inventory_df["display_format"].value_counts()

    redir_ids = deceit_df.loc[deceit_df["deceit_type"].isin(["single_redirect", "multi_redirect"]), "ad_id"]
    redir_per_fmt = deceit_df[deceit_df["ad_id"].isin(set(redir_ids))].drop_duplicates("ad_id")["display_format"].value_counts()

    plot_bar_chart(100 * redir_per_fmt / fmt_totals.reindex(redir_per_fmt.index), title="redirections")

    plot_ctas(inventory_df, redir_ids, 200, f"{redir_ids.nunique()} redirects CTAs")
    innocent_ids = inventory_df.loc[~inventory_df["ad_id"].isin(deceit_df["ad_id"]), "ad_id"]
    plot_ctas(inventory_df, get_sample(innocent_ids, len(redir_ids)), 200, "normal")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DB_PATH,
                        help="SQLite advert database (default: %(default)s)")
    parser.add_argument("--redir-dir", type=Path, default=REDIR_RESULTS_DIR,
                        help="directory of redirection probe JSON results (default: %(default)s)")
    parser.add_argument("--persist", action="store_true",
                        help="save the scan data frames as *.parquet in CWD (needs pyarrow)")
    parser.add_argument("--smoke", action="store_true",
                        help="run the display-format smoke test before scanning")
    return parser.parse_args(argv)


def main(argv=None, report=False):
    """Full pipeline; returns (inventory_df, deceit_df, masks_df, pairs_df)."""
    args = parse_args(argv)

    db = get_db_connection(args.db)
    if args.smoke:
        smoke_test_displays(db)

    ad_ids = get_ad_ids(db)
    redir_strata = classify_redirections(load_redirection_results(args.redir_dir))
    single_redirect_domains = frozenset(redir_strata["single"])
    multi_redirect_domains = frozenset(redir_strata["multi"])

    inventory_df, deceit_df, masks_df, pairs_df = scan_ads(
        db, ad_ids, single_redirect_domains, multi_redirect_domains)

    # Persist so plot-tweaking sessions don't re-trigger a 400k-ad scan.
    if args.persist:
        save_parquet({"inventory_df": inventory_df, "deceit_df": deceit_df,
                      "masks_df": masks_df, "pairs_df": pairs_df})

    if report:
        report_deception_stats(inventory_df, deceit_df)
        report_owner_analysis(deceit_df)
        report_url_masking(inventory_df, deceit_df, masks_df)
        report_card_cloaking(inventory_df, deceit_df)
        report_redirection_cloaking(inventory_df, deceit_df)

    db.close()
    return inventory_df, deceit_df, masks_df, pairs_df


if __name__ == "__main__":
    inv_df, deceit_df, masks_df, pairs_df = main()
    print(pairs_df.to_csv())
