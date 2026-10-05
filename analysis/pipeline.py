#!/usr/bin/env python3
"""One-pass analysis pipeline for the Meta Ad Library URL study.

The pipeline combines the exploratory scripts in ``analysis/legacy`` into a
single reproducible run. It reads only local inputs (it never fetches an ad,
opens a URL, or calls an image-classification service):

* a SQLite database with ``advert(ad_archive_id, metadata)`` (and, optionally,
  ``ad_media(hash, ad_archive_id, ...)``),
* the four geolocated redirection-result JSON files,
* optional image-label CSV/JSONL or the ``results`` SQLite database emitted by
  the legacy ``extract_media.py`` script, and
* an optional Tranco ``rank,domain`` CSV.

Typical full run::

    python analysis/pipeline.py \\
      --db /path/to/full_lighsnap.db \\
      --redirections data/redirection_results \\
      --image-labels /path/to/image_labels.csv \\
      --tranco /path/to/tranco.csv \\
      --out analysis/output/run-2026-10-05 --plots

A redirection-only run is also possible with the repository's checked-in
probe files. See ``analysis/README.md`` for input contracts, definitions, and
interpretation cautions.

Core analysis uses the Python standard library. ``tldextract`` is strongly
recommended for Public Suffix List (PSL) handling; without it a documented,
limited fallback is used. ``matplotlib`` is optional and is only needed for
``--plots``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import ipaddress
import json
import math
import os
import re
import sqlite3
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

try:  # High-quality PSL and private-suffix handling; network access disabled.
    import tldextract  # type: ignore

    _TLDEXTRACT = tldextract.TLDExtract(
        suffix_list_urls=(), include_psl_private_domains=True
    )
except ImportError:  # pragma: no cover - tested through the stdlib fallback.
    tldextract = None
    _TLDEXTRACT = None

try:
    _TLDEXTRACT_VERSION = package_version("tldextract")
except PackageNotFoundError:
    _TLDEXTRACT_VERSION = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REDIRECTIONS = ROOT / "data" / "redirection_results"
DEFAULT_OUT = ROOT / "analysis" / "output" / "latest"

# Meta-owned destination domains used in the paper draft's ecosystem-circularity
# analysis. These are a seed list, not a canonical inventory of Meta properties.
META_DOMAINS = {
    "facebook.com", "fb.com", "fb.me", "instagram.com", "whatsapp.com",
    "wa.me", "messenger.com", "meta.com", "threads.net",
}

# Conservative, editable seed list. A match means "known-shortener candidate";
# it does not imply abuse. Add platform-specific services only with a stated rule.
SHORTENER_DOMAINS = {
    "bit.ly", "bitly.com", "t.co", "tinyurl.com", "goo.gl", "ow.ly",
    "buff.ly", "is.gd", "rebrand.ly", "lnkd.in", "shorturl.at",
    "forms.gle", "youtu.be", "t.me",
}

# Used only when tldextract is unavailable. This is intentionally small and is
# not a replacement for a dated Public Suffix List.
_COMMON_MULTI_LABEL_SUFFIXES = {
    "ac.uk", "co.uk", "gov.uk", "org.uk", "com.au", "net.au", "org.au",
    "co.nz", "org.nz", "co.jp", "co.kr", "co.in", "com.cn", "com.hk",
    "com.sg", "com.mx", "com.ar", "com.br", "net.br", "org.br", "gov.br",
    "com.tr", "com.tw", "com.my", "com.ph", "com.vn", "com.ua", "co.za",
    "com.ng", "com.eg", "com.sa", "com.pk", "com.bd", "com.pe", "com.co",
}

COUNTRY_NAMES = {
    "alemanha": "DE", "germany": "DE", "de": "DE",
    "brasil": "BR", "brazil": "BR", "br": "BR",
    "eua": "US", "usa": "US", "united_states": "US", "us": "US",
    "portugal": "PT", "pt": "PT",
}

AD_FIELDS = [
    "ad_archive_id", "owner_id", "display_format", "cta_type",
    "publisher_platforms", "page_entity_type", "page_categories",
    "page_category_count", "start_date_raw", "end_date_raw",
    "total_active_time_raw", "active_lifetime_days",
    "has_start_date", "has_end_date", "has_total_active_time",
    "has_url", "url_count", "unique_url_count", "unique_link_domains",
    "n_cards", "n_card_domains", "card_domain_heterogeneity_candidate",
    "url_masking_candidate", "single_external_destination_url",
    "multiple_destinations_url_candidate", "single_external_destination_domain_legacy",
    "multiple_destinations_domain_legacy", "any_cloaking_url_scope",
    "any_cloaking_domain_legacy_scope", "body_chars", "title_chars",
    "link_description_chars", "caption_chars", "media_asset_count",
    "labelled_image_count", "image_label_count", "image_labels",
]
URL_FIELDS = [
    "ad_archive_id", "owner_id", "display_format", "link_position",
    "card_position", "url_id", "url_domain", "url_suffix", "url_scheme",
    "url_path_chars", "url_path_depth", "url_has_query", "caption_domain",
    "url_masking_candidate", "redirect_status_url_exact",
    "redirect_status_domain_legacy", "redirect_match_method",
    "country_outcomes_differ", "distinct_final_domains", "final_domains",
]
METADATA_AVAILABILITY_FIELDS = [
    "field", "ads_scanned", "non_missing_ads", "missing_ads",
    "availability_pct", "distinct_values_observed", "top_values",
    "notes",
]
REDIRECT_URL_FIELDS = [
    "url_id", "source_domain", "url_scope_status", "final_domain_count",
    "final_domains", "countries_with_success", "countries_with_error",
    "successful_observations", "error_observations", "country_outcomes_differ",
    "within_country_variation",
]
REDIRECT_EDGE_FIELDS = ["source_domain", "destination_domain", "country", "requested_urls"]
FORMAT_FIELDS = [
    "display_format", "ads", "ads_with_url", "url_masking_candidate_ads",
    "card_domain_heterogeneity_candidate_ads", "single_external_destination_url_ads",
    "multiple_destinations_url_candidate_ads", "single_external_destination_domain_legacy_ads",
    "multiple_destinations_domain_legacy_ads", "any_cloaking_url_scope_ads",
    "any_cloaking_domain_legacy_scope_ads", "url_masking_rate_pct",
    "card_heterogeneity_rate_pct", "any_cloaking_url_scope_rate_pct",
    "any_cloaking_domain_legacy_rate_pct",
]
DOMAIN_FIELDS = [
    "domain", "public_suffix", "link_occurrences", "distinct_urls", "ads",
    "advertisers", "meta_owned_seed", "known_shortener_candidate",
    "tranco_rank", "redirect_status_domain_legacy",
]
TLD_FIELDS = [
    "public_suffix", "link_occurrences", "distinct_domains", "ad_domain_occurrences",
    "advertisers", "meta_owned_domain_count", "known_shortener_domain_count",
]
TLD_STRATA_FIELDS = [
    "advertiser_stratum", "public_suffix", "domains", "advertiser_weighted_domains",
    "link_occurrences", "share_domains_pct", "share_advertiser_weight_pct",
    "share_link_occurrences_pct",
]
MASK_EDGE_FIELDS = ["mask_domain", "target_domain", "pair_occurrences", "ads", "advertisers"]
MASK_DOMAIN_FIELDS = ["mask_domain", "pair_occurrences", "ads", "distinct_targets", "tranco_rank"]
RQ3_FIELDS = [
    "outcome_scope", "feature", "category", "eligible_ads", "cloaked_ads",
    "noncloaked_ads", "cloaked_with_feature", "noncloaked_with_feature",
    "cloaked_rate_pct", "noncloaked_rate_pct", "risk_difference_pp",
    "risk_difference_95_low_pp", "risk_difference_95_high_pp", "risk_ratio",
    "odds_ratio", "odds_ratio_95_low", "odds_ratio_95_high", "p_value_pearson",
    "p_value_bh_fdr", "positive_ads", "meets_minimum_cell_count",
]
CONTINUOUS_FIELDS = [
    "outcome_scope", "feature", "cloaked_n", "cloaked_mean", "cloaked_sd",
    "noncloaked_n", "noncloaked_mean", "noncloaked_sd", "mean_difference",
]


@dataclass(frozen=True)
class URLParts:
    raw: str
    scheme: str
    host: str
    registered_domain: str
    public_suffix: str
    path: str
    has_query: bool


def _normalise_host(host: str) -> str:
    host = (host or "").strip().strip(".").lower()
    if host.startswith("www."):
        host = host[4:]
    try:
        return host.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        return host


def domain_parts(host: str) -> tuple[str, str]:
    """Return (registrable domain, public suffix) for a host.

    ``tldextract`` uses its bundled PSL snapshot because ``suffix_list_urls`` is
    empty. The fallback supports common multi-label suffixes but is deliberately
    not described as PSL-equivalent.
    """
    host = _normalise_host(host)
    if not host:
        return "", ""
    try:
        ipaddress.ip_address(host.strip("[]"))
        return host, ""
    except ValueError:
        pass

    if _TLDEXTRACT is not None:
        result = _TLDEXTRACT(host)
        registered = (result.top_domain_under_registry_suffix or "").lower()
        suffix = (result.suffix or "").lower()
        if registered:
            return registered, suffix
        # Preserve intranet/single-label hosts for diagnostics, not domain stats.
        return host, ""

    labels = [part for part in host.split(".") if part]
    if len(labels) < 2:
        return host, ""
    suffix2 = ".".join(labels[-2:])
    if suffix2 in _COMMON_MULTI_LABEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:]), suffix2
    return suffix2, labels[-1]


def parse_url(value: Any) -> URLParts:
    """Parse a URL-like value without retaining query values in outputs."""
    raw = html.unescape(str(value or "")).strip()
    if not raw:
        return URLParts("", "", "", "", "", "", False)
    candidate = raw
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    elif not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", candidate):
        candidate = "https://" + candidate
    try:
        parsed = urlsplit(candidate)
        host = _normalise_host(parsed.hostname or "")
        scheme = (parsed.scheme or "").lower()
        path = parsed.path or "/"
    except (ValueError, UnicodeError):
        return URLParts(raw, "", "", "", "", "", False)
    registered, suffix = domain_parts(host)
    return URLParts(raw, scheme, host, registered, suffix, path, bool(parsed.query))


def canonical_url(value: Any) -> str:
    """Canonical URL key for matching probe inputs to ad URLs.

    Scheme/host case and fragments are normalized; path and query are preserved
    because collapsing them can merge different redirect endpoints. The returned
    key is internal and is never written to CSV unless the user explicitly opts
    in to sensitive raw URL output.
    """
    parts = parse_url(value)
    if not parts.host:
        return ""
    parsed = urlsplit(parts.raw if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", parts.raw) else "https://" + parts.raw)
    host = parts.host
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = host
    if port and not ((parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    return urlunsplit((parts.scheme or "https", netloc, parsed.path or "/", parsed.query, ""))


def stable_url_id(value: Any) -> str:
    key = canonical_url(value) or str(value or "").strip().lower()
    return hashlib.sha256(key.encode("utf-8", errors="replace")).hexdigest()[:20] if key else ""


_CAPTION_DOMAIN_RE = re.compile(
    r"(?<![@\w-])(?:https?://)?(?:www\.)?"
    r"(?:[A-Z0-9\u0080-\uffff](?:[A-Z0-9\u0080-\uffff-]{0,61}[A-Z0-9\u0080-\uffff])?\.)+"
    r"[A-Z\u0080-\uffff]{2,63}(?::\d{1,5})?(?:/[^\s<>]*)?",
    re.IGNORECASE,
)


def caption_domain(value: Any) -> str:
    """Extract a domain only when caption text contains a URL-like hostname."""
    text = html.unescape(str(value or "")).strip()
    if not text:
        return ""
    match = _CAPTION_DOMAIN_RE.search(text)
    if not match:
        return ""
    candidate = match.group(0).rstrip(".,;:!?)]}>'\"»”’")
    return parse_url(candidate).registered_domain


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return " ".join(_as_text(item) for item in value if item is not None).strip()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _category_values(value: Any) -> list[str]:
    """Normalize a scalar/list/JSON model response into non-empty label strings."""
    if value is None:
        return []
    if isinstance(value, dict):
        for key in ("labels", "categories", "label", "category", "class", "classes", "predicted_label"):
            if key in value:
                return _category_values(value[key])
        return []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            out.extend(_category_values(item))
        return out
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "nan", "n/a", "unknown"}:
        return []
    if text[:1] in "[{\"":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if parsed is not None and parsed != text:
            return _category_values(parsed)
    # Pipe/semicolon/newline are common explicit multi-label separators. Do not
    # split commas in free-form model prose, where they may be part of a label.
    parts = re.split(r"[|;\n]+", text)
    return sorted({p.strip().strip("\"'` ") for p in parts if p.strip().strip("\"'` ")})


def _numeric(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        number = float(str(value).replace(",", ""))
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def _has_metadata_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "null", "none", "nan", "n/a", "not available"}
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _parse_datetime_value(value: Any) -> datetime | None:
    """Parse common ISO/date and Unix timestamp encodings without guessing units.

    Numeric timestamps are interpreted by magnitude (seconds, milliseconds, or
    microseconds). This is used only for a derived start-to-end interval; the
    original fields are always retained in output so the conversion is auditable.
    """
    if not _has_metadata_value(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) or re.fullmatch(r"[+-]?\d+(?:\.\d+)?", str(value).strip()):
        number = _numeric(value)
        if number is None or number <= 0:
            return None
        # Compact calendar encodings, e.g. 20261005 or 20261005153000.
        digits = str(int(number))
        try:
            if len(digits) == 8:
                return datetime.strptime(digits, "%Y%m%d").replace(tzinfo=timezone.utc)
            if len(digits) == 14:
                return datetime.strptime(digits, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        seconds = number
        if number >= 1e15:
            seconds = number / 1e6
        elif number >= 1e12:
            seconds = number / 1e3
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    text = str(value).strip()
    iso_text = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(iso_text)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, date_format).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _active_lifetime_days(start_value: Any, end_value: Any) -> float | None:
    start = _parse_datetime_value(start_value)
    end = _parse_datetime_value(end_value)
    if start is None or end is None:
        return None
    duration = (end - start).total_seconds() / 86400
    if duration < 0:
        return None
    return round(duration, 3)


def _read_only_sqlite(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"SQLite input does not exist: {path}")
    uri = path.resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _country_code(stem: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    return COUNTRY_NAMES.get(normalized, stem.upper())


def _observation_domain(value: Any) -> str:
    if not value:
        return ""
    value_text = str(value).strip()
    if value_text.lower() in {"errored out", "error", "timeout", "timed out", "blocked", "failed"}:
        return ""
    return parse_url(value_text).registered_domain


def classify_destinations(source_domain: str, final_domains: Iterable[str]) -> str:
    """Classify observed destination domains, not the number of HTTP hops."""
    finals = {x for x in final_domains if x}
    if not finals:
        return "unresolved"
    if len(finals) > 1:
        return "multiple_destinations"
    final = next(iter(finals))
    if source_domain and final == source_domain:
        return "same_registered_domain"
    return "single_external_destination"


def load_redirection_results(directory: Path | None) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Load the per-country JSON results by canonical *input URL*.

    Each JSON value is treated as a collection of observed final URLs. Error
    sentinels are counted but never converted into domains. This data does not
    encode intermediate HTTP hops, so the pipeline never labels destination
    count as redirect-chain length.
    """
    if directory is None or not directory.exists():
        return {}, {"files": [], "warnings": [f"No redirection directory: {directory}"]}
    files = sorted(directory.glob("*.json"))
    results: dict[str, dict[str, Any]] = {}
    key_sets: dict[str, set[str]] = {}
    warnings: list[str] = []
    file_summaries: list[dict[str, Any]] = []

    for path in files:
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"Could not read {path.name}: {exc}")
            continue
        if not isinstance(content, dict):
            warnings.append(f"{path.name} is not a JSON object; skipped")
            continue
        metadata = content.get("metadata", {})
        records = {k: v for k, v in content.items() if k != "metadata"}
        declared = metadata.get("total") if isinstance(metadata, dict) else None
        if declared is not None and declared != len(records):
            warnings.append(f"{path.name}: metadata.total={declared}, records={len(records)}")
        country = _country_code(path.stem)
        normalized_keys: set[str] = set()
        record_count = 0
        error_observations = 0
        for requested_url, raw_values in records.items():
            key = canonical_url(requested_url)
            if not key:
                warnings.append(f"{path.name}: unparseable requested URL (id {stable_url_id(requested_url)})")
                continue
            normalized_keys.add(key)
            if not isinstance(raw_values, list):
                raw_values = [raw_values]
            domains: set[str] = set()
            successful_values = 0
            errors = 0
            for raw_value in raw_values:
                record_count += 1
                destination = _observation_domain(raw_value)
                if not destination:
                    errors += 1
                    error_observations += 1
                    continue
                successful_values += 1
                domains.add(destination)
            slot = results.setdefault(key, {
                "requested_url": str(requested_url),
                "url_id": stable_url_id(requested_url),
                "source_domain": parse_url(requested_url).registered_domain,
                "per_country": {},
            })
            if country in slot["per_country"]:
                warnings.append(f"Duplicate country stem {country}; later file overwrote earlier values")
            slot["per_country"][country] = {
                "final_domains": sorted(domains),
                "success_observations": successful_values,
                "error_observations": errors,
                "raw_observations": len(raw_values),
                "status": classify_destinations(slot["source_domain"], domains),
            }
        key_sets[path.stem] = normalized_keys
        file_summaries.append({
            "file": path.name,
            "country": country,
            "requested_urls": len(normalized_keys),
            "raw_observations": record_count,
            "error_observations": error_observations,
            "declared_total": declared,
            "metadata_errors": metadata.get("errors") if isinstance(metadata, dict) else None,
            "metadata_completed": metadata.get("completed") if isinstance(metadata, dict) else None,
        })

    if key_sets:
        names = list(key_sets)
        base_name = names[0]
        base = key_sets[base_name]
        union = set().union(*key_sets.values())
        intersection = set.intersection(*key_sets.values()) if key_sets else set()
        for name, values in key_sets.items():
            if values != base:
                warnings.append(
                    f"Probe URL coverage differs: {name} has {len(values - base)} additional and "
                    f"{len(base - values)} missing canonical URLs relative to {base_name}"
                )
    else:
        union, intersection = set(), set()
    diagnostics = {
        "files": file_summaries,
        "warnings": warnings,
        "canonical_requested_urls_union": len(union),
        "canonical_requested_urls_intersection": len(intersection),
        "source_url_key_sets_match": bool(key_sets) and len(union) == len(intersection),
        "domain_parser": "tldextract bundled PSL" if _TLDEXTRACT is not None else "limited stdlib suffix fallback",
    }
    return results, diagnostics


def summarize_redirections(
    url_results: Mapping[str, Mapping[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]],
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]],
]:
    """Return URL summaries, legacy eTLD+1 summaries, and source->final edges."""
    url_summaries: dict[str, dict[str, Any]] = {}
    legacy: dict[str, dict[str, Any]] = {}
    edge_counter: Counter[tuple[str, str, str]] = Counter()
    country_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for key, record in url_results.items():
        src = str(record.get("source_domain", ""))
        per_country = record.get("per_country", {})
        all_final_domains: set[str] = set()
        countries_success: list[str] = []
        countries_error: list[str] = []
        successful_observations = 0
        error_observations = 0
        country_signatures: list[frozenset[str]] = []
        within_country_variation = False
        for country, outcome in per_country.items():
            finals = set(outcome.get("final_domains", []))
            all_final_domains.update(finals)
            successful_observations += int(outcome.get("success_observations", 0))
            error_observations += int(outcome.get("error_observations", 0))
            if finals:
                countries_success.append(country)
                country_signatures.append(frozenset(finals))
            if int(outcome.get("error_observations", 0)):
                countries_error.append(country)
            if len(finals) > 1:
                within_country_variation = True
            country_counts[country][outcome.get("status", "unresolved")] += 1
            for destination in finals:
                edge_counter[(src, destination, country)] += 1
        status = classify_destinations(src, all_final_domains)
        signatures_differ = len(set(country_signatures)) > 1
        url_summaries[key] = {
            "url_id": record.get("url_id", ""),
            "source_domain": src,
            "final_domains": sorted(all_final_domains),
            "status": status,
            "countries_with_success": sorted(countries_success),
            "countries_with_error": sorted(countries_error),
            "successful_observations": successful_observations,
            "error_observations": error_observations,
            "country_outcomes_differ": signatures_differ,
            "within_country_variation": within_country_variation,
            "per_country": per_country,
        }
        group = legacy.setdefault(src, {
            "final_domains": set(), "url_count": 0, "url_statuses": Counter(),
            "country_final_domains": defaultdict(set), "country_url_count": Counter(),
        })
        group["url_count"] += 1
        group["final_domains"].update(all_final_domains)
        group["url_statuses"][status] += 1
        for country, outcome in per_country.items():
            group["country_url_count"][country] += 1
            group["country_final_domains"][country].update(outcome.get("final_domains", []))

    legacy_rows: list[dict[str, Any]] = []
    for source, group in legacy.items():
        finals = set(group["final_domains"])
        country_sets = [frozenset(x) for x in group["country_final_domains"].values() if x]
        legacy[source] = {
            **group,
            "status": classify_destinations(source, finals),
            "country_outcomes_differ": len(set(country_sets)) > 1,
            "final_domains": finals,
        }
        legacy_rows.append({
            "source_domain": source,
            "requested_url_count": group["url_count"],
            "legacy_domain_status": classify_destinations(source, finals),
            "distinct_final_domains": len(finals),
            "final_domains": "|".join(sorted(finals)),
            "country_outcomes_differ": len(set(country_sets)) > 1,
            "url_statuses": json.dumps(dict(group["url_statuses"]), sort_keys=True),
        })

    edges = [
        {"source_domain": src, "destination_domain": dst, "country": country, "requested_urls": n}
        for (src, dst, country), n in sorted(edge_counter.items(), key=lambda x: (-x[1], x[0]))
    ]
    country_rows = [
        {"country": country, "url_scope_status": status, "requested_urls": count}
        for country, counts in sorted(country_counts.items())
        for status, count in sorted(counts.items())
    ]
    return url_summaries, legacy, edges, country_rows, legacy_rows


def _find_column(columns: set[str], candidates: Sequence[str]) -> str | None:
    lower = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def load_media_associations(conn: sqlite3.Connection) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return asset-hash -> ad IDs and ad ID -> asset hashes from ad_media."""
    if not _table_exists(conn, "ad_media"):
        return {}, {}
    columns = _table_columns(conn, "ad_media")
    hash_col = _find_column(columns, ("hash", "media_hash", "asset_hash"))
    ad_col = _find_column(columns, ("ad_archive_id", "ad_id", "advert_id"))
    if not hash_col or not ad_col:
        return {}, {}
    # Identifiers are selected only from PRAGMA-discovered column names.
    sql = f'SELECT "{hash_col}", "{ad_col}" FROM ad_media WHERE "{hash_col}" IS NOT NULL'
    asset_to_ads: dict[str, set[str]] = defaultdict(set)
    ads_to_assets: dict[str, set[str]] = defaultdict(set)
    for media_hash, ad_id in conn.execute(sql):
        if media_hash is None or ad_id is None:
            continue
        h, a = str(media_hash), str(ad_id)
        asset_to_ads[h].add(a)
        ads_to_assets[a].add(h)
    return dict(asset_to_ads), dict(ads_to_assets)


def _iter_label_rows(path: Path, model: str | None) -> tuple[Iterator[dict[str, Any]], str]:
    """Create a row iterator for CSV/TSV, JSON/JSONL, or legacy SQLite results."""
    suffix = path.suffix.lower()
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        conn = _read_only_sqlite(path)
        if not _table_exists(conn, "results"):
            conn.close()
            raise ValueError(f"{path} is SQLite but has no 'results' table")
        columns = _table_columns(conn, "results")
        hash_col = _find_column(columns, ("hash", "media_hash", "image_hash"))
        response_col = _find_column(columns, ("response", "label", "labels", "classification"))
        model_col = _find_column(columns, ("model",))
        error_col = _find_column(columns, ("error",))
        format_col = _find_column(columns, ("format", "mime_type", "media_type"))
        if not hash_col or not response_col:
            conn.close()
            raise ValueError("SQLite 'results' table needs hash and response/label columns")
        select_cols = [hash_col, response_col]
        if model_col:
            select_cols.append(model_col)
        if error_col:
            select_cols.append(error_col)
        if format_col:
            select_cols.append(format_col)
        query = "SELECT " + ", ".join('"' + col + '"' for col in select_cols) + ' FROM "results"'

        def gen() -> Iterator[dict[str, Any]]:
            try:
                for row in conn.execute(query):
                    values = dict(zip(select_cols, row))
                    if model and model_col and str(values.get(model_col, "")) != model:
                        continue
                    if error_col and values.get(error_col):
                        continue
                    if format_col and values.get(format_col) and "image" not in str(values[format_col]).lower():
                        continue
                    yield {
                        "media_hash": values.get(hash_col),
                        "response": values.get(response_col),
                        "model": values.get(model_col, "") if model_col else "",
                    }
            finally:
                conn.close()
        return gen(), "media_hash"

    if not path.exists():
        raise FileNotFoundError(f"Image-label input does not exist: {path}")

    def gen_file() -> Iterator[dict[str, Any]]:
        if suffix in {".jsonl", ".ndjson"}:
            with path.open(encoding="utf-8-sig") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if isinstance(value, dict):
                        yield value
        elif suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, list):
                for row in value:
                    if isinstance(row, dict):
                        yield row
            elif isinstance(value, dict):
                if isinstance(value.get("data"), list):
                    for row in value["data"]:
                        if isinstance(row, dict):
                            yield row
                else:
                    for key, label in value.items():
                        if key != "metadata":
                            yield {"media_hash": key, "label": label}
        elif suffix in {".csv", ".tsv"}:
            delimiter = "\t" if suffix == ".tsv" else ","
            with path.open(newline="", encoding="utf-8-sig") as stream:
                for row in csv.DictReader(stream, delimiter=delimiter):
                    yield {str(k or "").strip(): v for k, v in row.items()}
        else:
            raise ValueError("Image labels must be CSV, TSV, JSON, JSONL/NDJSON, or a results SQLite DB")

    return gen_file(), "file"


def load_image_labels(
    path: Path | None,
    asset_to_ads: Mapping[str, set[str]],
    *,
    label_column: str = "auto",
    id_column: str = "auto",
    model: str | None = None,
    min_confidence: float | None = None,
) -> dict[str, Any]:
    """Load labels and aggregate each unique labeled asset to its associated ads.

    Rows may be keyed by ``media_hash``/``hash`` (preferred) or directly by
    ``ad_archive_id``/``ad_id``. A hash is joined through the database's
    ``ad_media`` table. Missing labels remain missing; they are never treated
    as a negative visual class.
    """
    if path is None:
        return {
            "labels_by_ad": {}, "labelled_assets": set(), "asset_labels": {},
            "direct_labelled_ads": set(), "diagnostics": {
                "input": None, "rows": 0, "labelled_assets": 0,
                "matched_assets": 0, "unmatched_assets": 0, "labelled_ads": 0,
                "labels": 0, "warnings": [],
            },
        }
    rows, row_source = _iter_label_rows(path, model)
    labels_by_asset: dict[str, set[str]] = defaultdict(set)
    labels_by_ad: dict[str, set[str]] = defaultdict(set)
    labelled_assets: set[str] = set()
    direct_labelled_ads: set[str] = set()
    warnings: list[str] = []
    row_count = 0
    skipped_confidence = 0
    matched_assets: set[str] = set()
    unmatched_assets: set[str] = set()
    seen_labels: set[str] = set()

    for row in rows:
        row_count += 1
        normalized_keys = {str(k).strip().lower(): k for k in row}
        id_key = (
            normalized_keys.get(id_column.lower()) if id_column.lower() != "auto" else None
        )
        if id_key is None:
            id_key = next((normalized_keys[k] for k in (
                "media_hash", "image_hash", "asset_hash", "file_hash", "hash",
                "media_id", "image_id", "asset_id", "ad_archive_id", "ad_id",
            ) if k in normalized_keys), None)
        if id_key is None:
            if row_count == 1:
                warnings.append("No recognized ID column (expected media_hash/hash or ad_archive_id/ad_id)")
            continue
        identifier = str(row.get(id_key) or "").strip()
        if not identifier:
            continue

        if label_column.lower() == "auto":
            value_key = next((normalized_keys[k] for k in (
                "label", "labels", "category", "categories", "class", "classes",
                "predicted_label", "classification", "response", "result",
            ) if k in normalized_keys), None)
        else:
            value_key = normalized_keys.get(label_column.lower())
        if value_key is None:
            if row_count == 1:
                warnings.append(f"Could not find requested label column {label_column!r}")
            continue

        confidence_key = next((normalized_keys[k] for k in ("confidence", "score", "probability") if k in normalized_keys), None)
        if min_confidence is not None and confidence_key is not None:
            confidence = _numeric(row.get(confidence_key))
            if confidence is not None and confidence < min_confidence:
                skipped_confidence += 1
                continue

        values = _category_values(row.get(value_key))
        if not values:
            continue
        seen_labels.update(values)

        # Direct ad-level rows are accepted for pre-aggregated label files.
        id_name = str(id_key).lower()
        if id_name in {"ad_archive_id", "ad_id"}:
            direct_labelled_ads.add(identifier)
            labels_by_ad[identifier].update(values)
        else:
            labels_by_asset[identifier].update(values)
            labelled_assets.add(identifier)
            associated_ads = asset_to_ads.get(identifier, set())
            if associated_ads:
                matched_assets.add(identifier)
                for ad_id in associated_ads:
                    labels_by_ad[ad_id].update(values)
            else:
                unmatched_assets.add(identifier)

    # Count distinct linked classified assets per ad; asset hashes, not label rows.
    labelled_asset_count_by_ad: Counter[str] = Counter()
    for asset in matched_assets:
        for ad_id in asset_to_ads.get(asset, set()):
            labelled_asset_count_by_ad[ad_id] += 1
    return {
        "labels_by_ad": dict(labels_by_ad),
        "labelled_assets": labelled_assets,
        "asset_labels": dict(labels_by_asset),
        "labelled_asset_count_by_ad": labelled_asset_count_by_ad,
        "direct_labelled_ads": direct_labelled_ads,
        "diagnostics": {
            "input": path.name,
            "rows": row_count,
            "labelled_assets": len(labelled_assets),
            "matched_assets": len(matched_assets),
            "unmatched_assets": len(unmatched_assets),
            "direct_labelled_ads": len(direct_labelled_ads),
            "labelled_ads": len(labels_by_ad),
            "distinct_labels": len(seen_labels),
            "skipped_below_min_confidence": skipped_confidence,
            "label_column": label_column,
            "id_column": id_column,
            "model_filter": model,
            "row_source": row_source,
            "warnings": warnings,
        },
    }


def _bucket(value: int, boundaries: Sequence[tuple[int, int | None, str]]) -> str:
    for low, high, label in boundaries:
        if value >= low and (high is None or value <= high):
            return label
    return "unknown"


def advertiser_stratum(n: int) -> str:
    if n <= 0:
        return "unknown"
    if n == 1:
        return "1"
    if n <= 10:
        return "2-10"
    if n <= 100:
        return "11-100"
    if n <= 1000:
        return "101-1000"
    return ">1000"


def _lifetime_bucket(days: float | None) -> str:
    if days is None:
        return "not_computable"
    if days <= 1:
        return "≤1 day"
    if days <= 7:
        return "2–7 days"
    if days <= 30:
        return "8–30 days"
    if days <= 90:
        return "31–90 days"
    if days <= 365:
        return "91–365 days"
    return ">365 days"


def _metadata_link_entries(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    cards = snapshot.get("cards")
    entries: list[dict[str, Any]] = []
    if isinstance(cards, list) and cards:
        for index, card in enumerate(cards):
            if not isinstance(card, dict):
                continue
            if card.get("link_url") or card.get("caption"):
                entries.append({
                    "link_url": _as_text(card.get("link_url")),
                    "caption": _as_text(card.get("caption")),
                    "link_description": _as_text(card.get("link_description")),
                    "card_position": index,
                })
    if not entries and (snapshot.get("link_url") or snapshot.get("caption")):
        entries.append({
            "link_url": _as_text(snapshot.get("link_url")),
            "caption": _as_text(snapshot.get("caption")),
            "link_description": _as_text(snapshot.get("link_description")),
            "card_position": "",
        })
    return entries


def _iter_distinct_platforms(value: Any) -> list[str]:
    if isinstance(value, str):
        values = re.split(r"[,|;]+", value)
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = []
    return sorted({str(item).strip() for item in values if str(item).strip()})


def _clean_category_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values: Iterable[Any] = re.split(r"[|;]+", value)
    elif isinstance(value, (list, tuple, set)):
        values = value
    elif isinstance(value, dict):
        values = [value]
    else:
        values = []
    normalized: set[str] = set()
    for item in values:
        if isinstance(item, dict):
            item = next((item[key] for key in ("name", "label", "category", "title") if item.get(key)), "")
        text = str(item).strip() if item is not None else ""
        if text:
            normalized.add(text)
    return sorted(normalized)


class OnlineMoments:
    """Small-memory running mean and sample standard deviation."""
    def __init__(self) -> None:
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0

    def add(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)

    @property
    def sd(self) -> float:
        return math.sqrt(self.m2 / (self.n - 1)) if self.n > 1 else 0.0


def _chi_square_p_1df(a: int, b: int, c: int, d: int) -> float:
    """Uncorrected Pearson chi-square p-value, 1 df (large-sample approximation)."""
    n = a + b + c + d
    denominator = (a + b) * (c + d) * (a + c) * (b + d)
    if n == 0 or denominator == 0:
        return 1.0
    chi_square = n * (a * d - b * c) ** 2 / denominator
    return math.erfc(math.sqrt(chi_square / 2.0))


def _comparison_row(
    *, scope: str, feature: str, category: str, eligible_ads: int,
    cloaked_ads: int, positive_cloaked: int, positive_noncloaked: int,
    min_positive: int,
) -> dict[str, Any]:
    noncloaked_ads = eligible_ads - cloaked_ads
    negative_cloaked = cloaked_ads - positive_cloaked
    negative_noncloaked = noncloaked_ads - positive_noncloaked
    rate_c = positive_cloaked / cloaked_ads if cloaked_ads else 0.0
    rate_n = positive_noncloaked / noncloaked_ads if noncloaked_ads else 0.0
    rd = rate_c - rate_n
    rd_variance = (rate_c * (1.0 - rate_c) / cloaked_ads if cloaked_ads else 0.0) + (
        rate_n * (1.0 - rate_n) / noncloaked_ads if noncloaked_ads else 0.0
    )
    rd_se = math.sqrt(rd_variance)

    a, b, c, d = positive_cloaked, positive_noncloaked, negative_cloaked, negative_noncloaked
    # Haldane-Anscombe correction only for effect-size/CI stability; raw cells
    # and the Pearson p-value remain unmodified.
    aa, bb, cc, dd = (x + 0.5 for x in (a, b, c, d))
    odds_ratio = (aa * dd) / (bb * cc)
    log_or_se = math.sqrt(1.0 / aa + 1.0 / bb + 1.0 / cc + 1.0 / dd)
    log_or = math.log(odds_ratio)
    rr = (rate_c / rate_n) if rate_n else (math.inf if rate_c else 1.0)
    return {
        "outcome_scope": scope,
        "feature": feature,
        "category": category,
        "eligible_ads": eligible_ads,
        "cloaked_ads": cloaked_ads,
        "noncloaked_ads": noncloaked_ads,
        "cloaked_with_feature": positive_cloaked,
        "noncloaked_with_feature": positive_noncloaked,
        "cloaked_rate_pct": 100.0 * rate_c,
        "noncloaked_rate_pct": 100.0 * rate_n,
        "risk_difference_pp": 100.0 * rd,
        "risk_difference_95_low_pp": 100.0 * (rd - 1.96 * rd_se),
        "risk_difference_95_high_pp": 100.0 * (rd + 1.96 * rd_se),
        "risk_ratio": rr,
        "odds_ratio": odds_ratio,
        "odds_ratio_95_low": math.exp(log_or - 1.96 * log_or_se),
        "odds_ratio_95_high": math.exp(log_or + 1.96 * log_or_se),
        "p_value_pearson": _chi_square_p_1df(a, b, c, d),
        "p_value_bh_fdr": "",
        "positive_ads": positive_cloaked + positive_noncloaked,
        "meets_minimum_cell_count": positive_cloaked + positive_noncloaked >= min_positive,
    }


def _benjamini_hochberg(rows: list[dict[str, Any]], p_field: str, q_field: str) -> None:
    valid = [(i, float(row[p_field])) for i, row in enumerate(rows) if row.get(p_field) not in (None, "")]
    valid.sort(key=lambda item: item[1])
    m = len(valid)
    if not m:
        return
    adjusted = [1.0] * m
    running = 1.0
    for rank_index in range(m - 1, -1, -1):
        rank = rank_index + 1
        p_value = valid[rank_index][1]
        running = min(running, p_value * m / rank)
        adjusted[rank_index] = min(1.0, running)
    for (row_index, _), q_value in zip(valid, adjusted):
        rows[row_index][q_field] = q_value


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
            count += 1
    return count


def _load_tranco(path: Path | None) -> dict[str, int]:
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"Tranco file does not exist: {path}")
    ranks: dict[str, int] = {}
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        for row in reader:
            if not row:
                continue
            cells = [str(cell).strip() for cell in row]
            if len(cells) < 2:
                continue
            first, second = cells[0], cells[1]
            if first.lower() in {"rank", "position"} or second.lower() in {"domain", "url", "host"}:
                continue
            if first.isdigit():
                rank, value = int(first), second
            elif second.isdigit():
                rank, value = int(second), first
            else:
                continue
            domain = parse_url(value).registered_domain
            if domain:
                ranks[domain] = min(rank, ranks.get(domain, rank))
    return ranks


def _redirection_status_for_ad_url(
    url: str,
    url_results: Mapping[str, Mapping[str, Any]],
    url_summaries: Mapping[str, Mapping[str, Any]],
    legacy_domain_status: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str, str, list[str], bool]:
    key = canonical_url(url)
    if key in url_summaries:
        summary = url_summaries[key]
        domain_record = legacy_domain_status.get(parse_url(url).registered_domain, {})
        return (
            str(summary.get("status", "unresolved")),
            str(domain_record.get("status", "unresolved")),
            "url_exact",
            list(summary.get("final_domains", [])),
            bool(summary.get("country_outcomes_differ", False)),
        )
    source = parse_url(url).registered_domain
    if source and source in legacy_domain_status:
        record = legacy_domain_status[source]
        return (
            "not_probed_exact_url",
            str(record.get("status", "unresolved")),
            "domain_legacy_fallback",
            sorted(record.get("final_domains", set())),
            bool(record.get("country_outcomes_differ", False)),
        )
    return "not_probed", "not_probed", "none", [], False


def analyze_database(
    db_path: Path,
    out_dir: Path,
    *,
    url_results: Mapping[str, Mapping[str, Any]],
    url_summaries: Mapping[str, Mapping[str, Any]],
    legacy_domain_status: Mapping[str, Mapping[str, Any]],
    image_labels: Mapping[str, Any],
    tranco_ranks: Mapping[str, int],
    limit: int | None,
    include_sensitive_urls: bool,
    minimum_positive_cell: int,
) -> dict[str, Any]:
    """Stream metadata once; write RQ1/RQ2 outputs and accumulate RQ3 contrasts."""
    conn = _read_only_sqlite(db_path)
    if not _table_exists(conn, "advert"):
        conn.close()
        raise ValueError(f"{db_path} has no 'advert' table")
    advert_columns = _table_columns(conn, "advert")
    metadata_col = _find_column(advert_columns, ("metadata", "ad_metadata", "json"))
    id_col = _find_column(advert_columns, ("ad_archive_id", "ad_id", "id"))
    owner_col = _find_column(advert_columns, ("advertiser_id", "owner_id", "page_id"))
    format_col = _find_column(advert_columns, ("display_format", "format"))
    if not metadata_col:
        conn.close()
        raise ValueError("advert table must include a metadata JSON/text column")
    selected = [col for col in (id_col, metadata_col, owner_col, format_col) if col]
    select = ", ".join('"' + col + '"' for col in selected)
    query = f'SELECT {select} FROM "advert"'
    if limit is not None:
        query += f" LIMIT {int(limit)}"

    asset_to_ads, ads_to_assets = load_media_associations(conn)
    # Image-labels are loaded before the scan, so labels can be attached per ad.
    labels_by_ad = image_labels.get("labels_by_ad", {})
    labelled_asset_count_by_ad = image_labels.get("labelled_asset_count_by_ad", {})
    direct_labelled_ads = image_labels.get("direct_labelled_ads", set())
    n_db_media_ad_links = sum(len(assets) for assets in ads_to_assets.values())

    out_dir.mkdir(parents=True, exist_ok=True)
    ad_path = out_dir / "ad_inventory.csv"
    url_path = out_dir / "url_inventory.csv"
    mask_edges: Counter[tuple[str, str]] = Counter()
    mask_edge_ads: dict[tuple[str, str], set[str]] = defaultdict(set)
    mask_edge_owners: dict[tuple[str, str], set[str]] = defaultdict(set)
    domain_stats: dict[str, dict[str, Any]] = {}
    format_stats: dict[str, Counter[str]] = defaultdict(Counter)
    format_pattern_keys = [
        "url_masking_candidate", "card_domain_heterogeneity_candidate",
        "single_external_destination_url", "multiple_destinations_url_candidate",
        "single_external_destination_domain_legacy", "multiple_destinations_domain_legacy",
        "any_cloaking_url_scope", "any_cloaking_domain_legacy_scope",
    ]
    feature_positive: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    continuous: dict[tuple[str, str, str], OnlineMoments] = defaultdict(OnlineMoments)
    image_eligible_by_scope: Counter[str] = Counter()
    image_cloaked_by_scope: Counter[str] = Counter()
    domain_ad_counts: Counter[str] = Counter()
    metadata_presence: Counter[str] = Counter()
    metadata_values: dict[str, Counter[str]] = {
        field: Counter() for field in (
            "publisher_platform", "page_categories", "page_entity_type", "cta_type"
        )
    }
    total_ads = 0
    parse_errors = 0
    ads_with_url = 0
    link_occurrences = 0
    unique_url_ids: set[str] = set()
    ads_with_meta_domain = 0
    ads_with_label = 0
    url_match_methods: Counter[str] = Counter()

    try:
        ad_stream = conn.execute(query)
        with ad_path.open("w", newline="", encoding="utf-8") as ad_stream_out, url_path.open(
            "w", newline="", encoding="utf-8"
        ) as url_stream_out:
            ad_writer = csv.DictWriter(ad_stream_out, fieldnames=AD_FIELDS, extrasaction="ignore")
            url_fields = list(URL_FIELDS)
            if include_sensitive_urls:
                url_fields.extend(["raw_link_url", "raw_caption"])
            url_writer = csv.DictWriter(url_stream_out, fieldnames=url_fields, extrasaction="ignore")
            ad_writer.writeheader()
            url_writer.writeheader()

            for db_row in ad_stream:
                row_map = dict(zip(selected, db_row))
                raw_metadata = row_map.get(metadata_col)
                try:
                    if isinstance(raw_metadata, bytes):
                        raw_metadata = raw_metadata.decode("utf-8")
                    metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata
                    if not isinstance(metadata, dict):
                        raise ValueError("metadata is not an object")
                except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    parse_errors += 1
                    continue

                snapshot = metadata.get("snapshot")
                if not isinstance(snapshot, dict):
                    snapshot = {}
                ad_id = str(row_map.get(id_col) or metadata.get("ad_archive_id") or metadata.get("ad_id") or "")
                if not ad_id:
                    ad_id = f"row-{total_ads + parse_errors + 1}"
                owner = str(metadata.get("page_id") or row_map.get(owner_col) or "")
                fmt = str(snapshot.get("display_format") or row_map.get(format_col) or "unknown")
                cta_type = _as_text(snapshot.get("cta_type"))
                platforms = _iter_distinct_platforms(metadata.get("publisher_platform"))
                page_entity_type = _as_text(snapshot.get("page_entity_type") or metadata.get("page_entity_type"))
                categories_value = metadata.get("page_categories")
                if not _has_metadata_value(categories_value):
                    categories_value = snapshot.get("page_categories")
                categories = _clean_category_list(categories_value)
                start_date_raw = metadata.get("start_date")
                end_date_raw = metadata.get("end_date")
                total_active_time_raw = metadata.get("total_active_time")
                active_lifetime_days = _active_lifetime_days(start_date_raw, end_date_raw)
                body = _as_text(snapshot.get("body"))
                title = _as_text(snapshot.get("title"))
                link_description = _as_text(snapshot.get("link_description"))
                snapshot_caption = _as_text(snapshot.get("caption"))

                entries = _metadata_link_entries(snapshot)
                clean_links: list[dict[str, Any]] = []
                per_ad_domains: set[str] = set()
                per_ad_url_ids: set[str] = set()
                card_domains: set[str] = set()
                link_count = 0
                url_masked = False
                exact_single = False
                exact_multi = False
                domain_single = False
                domain_multi = False
                country_divergent = False
                for position, entry in enumerate(entries):
                    url = entry.get("link_url", "")
                    if not url:
                        continue
                    parts = parse_url(url)
                    if not parts.host or not parts.registered_domain:
                        # Non-HTTP pseudo-schemes (e.g. fbgeo://) are not web URLs.
                        continue
                    caption = entry.get("caption", "")
                    c_domain = caption_domain(caption)
                    is_masked = bool(c_domain and c_domain != parts.registered_domain)
                    exact_status, legacy_status, match_method, finals, divergent = _redirection_status_for_ad_url(
                        url, url_results, url_summaries, legacy_domain_status
                    )
                    url_match_methods[match_method] += 1
                    exact_single |= exact_status == "single_external_destination"
                    exact_multi |= exact_status == "multiple_destinations"
                    domain_single |= legacy_status == "single_external_destination"
                    domain_multi |= legacy_status == "multiple_destinations"
                    country_divergent |= divergent
                    url_masked |= is_masked
                    link_count += 1
                    link_id = stable_url_id(url)
                    per_ad_domains.add(parts.registered_domain)
                    per_ad_url_ids.add(link_id)
                    if entry.get("card_position") != "":
                        card_domains.add(parts.registered_domain)
                    clean_links.append({
                        **entry, "parts": parts, "caption_domain": c_domain,
                        "url_masked": is_masked, "url_id": link_id,
                        "exact_status": exact_status, "legacy_status": legacy_status,
                        "match_method": match_method, "final_domains": finals,
                        "country_divergent": divergent,
                    })

                # Card heterogeneity is the observable proxy; interpretation as
                # deception needs manual/content validation.
                has_card_format = fmt.upper() in {"DCO", "DPA", "CAROUSEL"} or bool(snapshot.get("cards"))
                card_candidate = bool(has_card_format and len(card_domains) > 1)
                url_candidate = bool(url_masked)
                exact_any = url_candidate or card_candidate or exact_multi or country_divergent
                legacy_any = url_candidate or card_candidate or domain_multi
                label_values = set(labels_by_ad.get(ad_id, set()))
                media_assets = ads_to_assets.get(ad_id, set())
                label_count = labelled_asset_count_by_ad.get(ad_id, 0)
                if ad_id in direct_labelled_ads and not label_count:
                    label_count = ""
                else:
                    label_count = int(label_count)
                if label_values:
                    ads_with_label += 1

                total_ads += 1
                field_presence = {
                    "publisher_platform": bool(platforms),
                    "page_categories": bool(categories),
                    "page_entity_type": _has_metadata_value(page_entity_type),
                    "cta_type": _has_metadata_value(cta_type),
                    "start_date": _has_metadata_value(start_date_raw),
                    "end_date": _has_metadata_value(end_date_raw),
                    "total_active_time": _has_metadata_value(total_active_time_raw),
                    "derived_active_lifetime_days": active_lifetime_days is not None,
                }
                for field, present in field_presence.items():
                    metadata_presence[field] += int(present)
                metadata_values["publisher_platform"].update(platforms)
                metadata_values["page_categories"].update(categories)
                if page_entity_type:
                    metadata_values["page_entity_type"][page_entity_type] += 1
                if cta_type:
                    metadata_values["cta_type"][cta_type] += 1
                if link_count:
                    ads_with_url += 1
                if any(domain in META_DOMAINS for domain in per_ad_domains):
                    ads_with_meta_domain += 1
                form = format_stats[fmt]
                form["ads"] += 1
                if link_count:
                    form["ads_with_url"] += 1
                flags = {
                    "url_masking_candidate": url_candidate,
                    "card_domain_heterogeneity_candidate": card_candidate,
                    "single_external_destination_url": exact_single,
                    "multiple_destinations_url_candidate": exact_multi,
                    "single_external_destination_domain_legacy": domain_single,
                    "multiple_destinations_domain_legacy": domain_multi,
                    "any_cloaking_url_scope": exact_any,
                    "any_cloaking_domain_legacy_scope": legacy_any,
                }
                for key, value in flags.items():
                    if value:
                        form[key] += 1

                for domain in per_ad_domains:
                    domain_ad_counts[domain] += 1
                for item in clean_links:
                    parts = item["parts"]
                    domain = parts.registered_domain
                    url_id = item["url_id"]
                    if domain not in domain_stats:
                        domain_stats[domain] = {
                            "public_suffix": parts.public_suffix,
                            "link_occurrences": 0,
                            "url_ids": set(),
                            "ads": 0,
                            "advertisers": set(),
                        }
                    stat = domain_stats[domain]
                    stat["link_occurrences"] += 1
                    stat["url_ids"].add(url_id)
                    if owner:
                        stat["advertisers"].add(owner)
                    if item["url_masked"]:
                        edge = (item["caption_domain"], domain)
                        mask_edges[edge] += 1
                        mask_edge_ads[edge].add(ad_id)
                        if owner:
                            mask_edge_owners[edge].add(owner)

                    line = {
                        "ad_archive_id": ad_id,
                        "owner_id": owner,
                        "display_format": fmt,
                        "link_position": position,
                        "card_position": item.get("card_position", ""),
                        "url_id": url_id,
                        "url_domain": domain,
                        "url_suffix": parts.public_suffix,
                        "url_scheme": parts.scheme,
                        "url_path_chars": len(parts.path),
                        "url_path_depth": len([p for p in parts.path.split("/") if p]),
                        "url_has_query": parts.has_query,
                        "caption_domain": item["caption_domain"],
                        "url_masking_candidate": item["url_masked"],
                        "redirect_status_url_exact": item["exact_status"],
                        "redirect_status_domain_legacy": item["legacy_status"],
                        "redirect_match_method": item["match_method"],
                        "country_outcomes_differ": item["country_divergent"],
                        "distinct_final_domains": len(item["final_domains"]),
                        "final_domains": "|".join(item["final_domains"]),
                    }
                    if include_sensitive_urls:
                        line["raw_link_url"] = item["link_url"]
                        line["raw_caption"] = item["caption"]
                    url_writer.writerow(line)
                    link_occurrences += 1
                    unique_url_ids.add(url_id)

                # The all-card domain count is reported for context even for ads
                # that do not satisfy the current card-pattern proxy.
                ad_fields = {
                    "ad_archive_id": ad_id,
                    "owner_id": owner,
                    "display_format": fmt,
                    "cta_type": cta_type,
                    "publisher_platforms": "|".join(platforms),
                    "page_entity_type": page_entity_type,
                    "page_categories": "|".join(categories),
                    "page_category_count": len(categories),
                    "start_date_raw": _as_text(start_date_raw),
                    "end_date_raw": _as_text(end_date_raw),
                    "total_active_time_raw": _as_text(total_active_time_raw),
                    "active_lifetime_days": active_lifetime_days if active_lifetime_days is not None else "",
                    "has_start_date": field_presence["start_date"],
                    "has_end_date": field_presence["end_date"],
                    "has_total_active_time": field_presence["total_active_time"],
                    "has_url": bool(link_count),
                    "url_count": link_count,
                    "unique_url_count": len(per_ad_url_ids),
                    "unique_link_domains": len(per_ad_domains),
                    "n_cards": len(snapshot.get("cards") or []) if isinstance(snapshot.get("cards"), list) else 0,
                    "n_card_domains": len(card_domains),
                    "card_domain_heterogeneity_candidate": card_candidate,
                    "url_masking_candidate": url_candidate,
                    "single_external_destination_url": exact_single,
                    "multiple_destinations_url_candidate": exact_multi,
                    "single_external_destination_domain_legacy": domain_single,
                    "multiple_destinations_domain_legacy": domain_multi,
                    "any_cloaking_url_scope": exact_any,
                    "any_cloaking_domain_legacy_scope": legacy_any,
                    "body_chars": len(body),
                    "title_chars": len(title),
                    "link_description_chars": len(link_description),
                    "caption_chars": len(snapshot_caption),
                    "media_asset_count": len(media_assets),
                    "labelled_image_count": label_count,
                    "image_label_count": len(label_values),
                    "image_labels": "|".join(sorted(label_values)),
                }
                ad_writer.writerow(ad_fields)

                for scope, outcome in (("url_exact", exact_any), ("domain_legacy", legacy_any)):
                    _update_feature_counts(
                        feature_positive, scope, "display_format", [fmt], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "cta_type", [cta_type or "missing"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "page_entity_type", [page_entity_type or "missing"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "publisher_platform", platforms or ["missing"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "page_category", categories or ["missing"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "has_start_date", ["yes" if field_presence["start_date"] else "no"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "has_end_date", ["yes" if field_presence["end_date"] else "no"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "has_total_active_time", ["yes" if field_presence["total_active_time"] else "no"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "active_lifetime_bucket", [_lifetime_bucket(active_lifetime_days)], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "has_url", ["yes" if link_count else "no"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "has_body_text", ["yes" if body else "no"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "has_title", ["yes" if title else "no"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "has_link_description", ["yes" if link_description else "no"], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "url_count_bucket", [_bucket(link_count, ((0, 0, "0"), (1, 1, "1"), (2, 4, "2-4"), (5, None, "5+")))], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "unique_domain_count_bucket", [_bucket(len(per_ad_domains), ((0, 0, "0"), (1, 1, "1"), (2, 4, "2-4"), (5, None, "5+")))], outcome
                    )
                    _update_feature_counts(
                        feature_positive, scope, "card_count_bucket", [_bucket(len(snapshot.get("cards") or []), ((0, 0, "0"), (1, 1, "1"), (2, 4, "2-4"), (5, None, "5+")))], outcome
                    )
                    for label in label_values:
                        _update_feature_counts(feature_positive, scope, "image_label", [label], outcome)
                    for value, name in (
                        (len(body), "body_chars"), (len(title), "title_chars"),
                        (len(link_description), "link_description_chars"),
                        (link_count, "url_count"), (len(per_ad_domains), "unique_link_domains"),
                        (len(media_assets), "media_asset_count"),
                        (active_lifetime_days, "active_lifetime_days"),
                    ):
                        if value is not None:
                            continuous[(scope, name, "cloaked" if outcome else "noncloaked")].add(float(value))
                    if label_values:
                        image_eligible_by_scope[scope] += 1
                        if outcome:
                            image_cloaked_by_scope[scope] += 1



    finally:
        conn.close()

    metadata_notes = {
        "publisher_platform": "Read from metadata.publisher_platform; multi-valued field.",
        "page_categories": "Read from metadata.page_categories, falling back to snapshot.page_categories; multi-valued field.",
        "page_entity_type": "Read from snapshot.page_entity_type, falling back to metadata.page_entity_type.",
        "cta_type": "Read from snapshot.cta_type.",
        "start_date": "Raw metadata.start_date retained; date encoding is not rewritten.",
        "end_date": "Raw metadata.end_date retained; missing end dates are not imputed.",
        "total_active_time": "Raw metadata.total_active_time retained; source unit is not assumed.",
        "derived_active_lifetime_days": "Only when start and end parse and end >= start; epoch unit inferred by magnitude or ISO/date parser.",
    }
    metadata_availability_rows = []
    for field, note in metadata_notes.items():
        present = metadata_presence[field]
        values = metadata_values.get(field, Counter())
        top_values = " | ".join(f"{value} ({count})" for value, count in values.most_common(10))
        metadata_availability_rows.append({
            "field": field,
            "ads_scanned": total_ads,
            "non_missing_ads": present,
            "missing_ads": total_ads - present,
            "availability_pct": 100.0 * present / total_ads if total_ads else 0.0,
            "distinct_values_observed": len(values) if field in metadata_values else "",
            "top_values": top_values,
            "notes": note,
        })
    _write_csv(out_dir / "metadata_field_availability.csv", METADATA_AVAILABILITY_FIELDS, metadata_availability_rows)

    # A domain can be linked by multiple ads; retain advertiser and ad counts.
    for domain, stat in domain_stats.items():
        stat["ads"] = domain_ad_counts.get(domain, 0)

    domain_rows: list[dict[str, Any]] = []
    for domain, stat in sorted(domain_stats.items(), key=lambda x: (-x[1]["link_occurrences"], x[0])):
        domain_rows.append({
            "domain": domain,
            "public_suffix": stat["public_suffix"],
            "link_occurrences": stat["link_occurrences"],
            "distinct_urls": len(stat["url_ids"]),
            "ads": stat["ads"],
            "advertisers": len(stat["advertisers"]),
            "meta_owned_seed": domain in META_DOMAINS,
            "known_shortener_candidate": domain in SHORTENER_DOMAINS,
            "tranco_rank": tranco_ranks.get(domain, ""),
            "redirect_status_domain_legacy": legacy_domain_status.get(domain, {}).get("status", "not_probed"),
        })
    _write_csv(out_dir / "domain_summary.csv", DOMAIN_FIELDS, domain_rows)

    tld_aggregate: dict[str, dict[str, Any]] = {}
    for domain, stat in domain_stats.items():
        suffix = stat["public_suffix"] or "unknown"
        tld = tld_aggregate.setdefault(suffix, {
            "public_suffix": suffix, "link_occurrences": 0, "distinct_domains": 0,
            "advertisers": set(), "meta_owned_domain_count": 0,
            "known_shortener_domain_count": 0,
        })
        tld["link_occurrences"] += stat["link_occurrences"]
        tld["distinct_domains"] += 1
        tld["advertisers"].update(stat["advertisers"])
        if domain in META_DOMAINS:
            tld["meta_owned_domain_count"] += 1
        if domain in SHORTENER_DOMAINS:
            tld["known_shortener_domain_count"] += 1
    # For TLD ad counts, sum per-domain ad counts. An ad using two domains in
    # the same suffix contributes twice; this is deliberately labeled as an
    # ad-domain occurrence count rather than a unique-ad count.
    tld_ad_counts: Counter[str] = Counter()
    for domain, stat in domain_stats.items():
        tld_ad_counts[stat["public_suffix"] or "unknown"] += stat["ads"]
    tld_rows = [{
        "public_suffix": suffix,
        "link_occurrences": stat["link_occurrences"],
        "distinct_domains": stat["distinct_domains"],
        "ad_domain_occurrences": tld_ad_counts.get(suffix, 0),
        "advertisers": len(stat["advertisers"]),
        "meta_owned_domain_count": stat["meta_owned_domain_count"],
        "known_shortener_domain_count": stat["known_shortener_domain_count"],
    } for suffix, stat in sorted(tld_aggregate.items(), key=lambda x: (-x[1]["link_occurrences"], x[0]))]
    _write_csv(out_dir / "tld_summary.csv", TLD_FIELDS, tld_rows)

    strata_tld: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    strata_totals: Counter[str] = Counter()
    for domain, stat in domain_stats.items():
        stratum = advertiser_stratum(len(stat["advertisers"]))
        suffix = stat["public_suffix"] or "unknown"
        strata_tld[(stratum, suffix)]["domains"] += 1
        strata_tld[(stratum, suffix)]["advertiser_weighted_domains"] += len(stat["advertisers"])
        strata_tld[(stratum, suffix)]["link_occurrences"] += stat["link_occurrences"]
        strata_totals[stratum] += 1
        strata_totals[stratum + "__advertiser_weighted"] += len(stat["advertisers"])
        strata_totals[stratum + "__links"] += stat["link_occurrences"]
    strata_rows = []
    for (stratum, suffix), values in sorted(strata_tld.items()):
        dtotal = strata_totals[stratum]
        atotal = strata_totals[stratum + "__advertiser_weighted"]
        ltotal = strata_totals[stratum + "__links"]
        strata_rows.append({
            "advertiser_stratum": stratum,
            "public_suffix": suffix,
            "domains": values["domains"],
            "advertiser_weighted_domains": values["advertiser_weighted_domains"],
            "link_occurrences": values["link_occurrences"],
            "share_domains_pct": 100 * values["domains"] / dtotal if dtotal else 0,
            "share_advertiser_weight_pct": 100 * values["advertiser_weighted_domains"] / atotal if atotal else 0,
            "share_link_occurrences_pct": 100 * values["link_occurrences"] / ltotal if ltotal else 0,
        })
    _write_csv(out_dir / "tld_by_advertiser_stratum.csv", TLD_STRATA_FIELDS, strata_rows)

    mask_edge_rows = []
    for edge, count in sorted(mask_edges.items(), key=lambda x: (-x[1], x[0])):
        mask_edge_rows.append({
            "mask_domain": edge[0], "target_domain": edge[1],
            "pair_occurrences": count, "ads": len(mask_edge_ads[edge]),
            "advertisers": len(mask_edge_owners[edge]),
        })
    _write_csv(out_dir / "mask_edges.csv", MASK_EDGE_FIELDS, mask_edge_rows)
    mask_domains: dict[str, dict[str, Any]] = {}
    for edge, count in mask_edges.items():
        entry = mask_domains.setdefault(edge[0], {"uses": 0, "ads": set(), "targets": set()})
        entry["uses"] += count
        entry["ads"].update(mask_edge_ads[edge])
        entry["targets"].add(edge[1])
    _write_csv(out_dir / "mask_domain_summary.csv", MASK_DOMAIN_FIELDS, (
        {
            "mask_domain": domain, "pair_occurrences": values["uses"],
            "ads": len(values["ads"]), "distinct_targets": len(values["targets"]),
            "tranco_rank": tranco_ranks.get(domain, ""),
        }
        for domain, values in sorted(mask_domains.items(), key=lambda x: (-x[1]["uses"], x[0]))
    ))

    format_rows = []
    for fmt, counts in sorted(format_stats.items(), key=lambda x: (-x[1]["ads"], x[0])):
        n = counts["ads"]
        row = {"display_format": fmt, "ads": n, "ads_with_url": counts["ads_with_url"]}
        for key in format_pattern_keys:
            row[key + "_ads"] = counts[key]
        row.update({
            "url_masking_rate_pct": 100 * counts["url_masking_candidate"] / n if n else 0,
            "card_heterogeneity_rate_pct": 100 * counts["card_domain_heterogeneity_candidate"] / n if n else 0,
            "any_cloaking_url_scope_rate_pct": 100 * counts["any_cloaking_url_scope"] / n if n else 0,
            "any_cloaking_domain_legacy_rate_pct": 100 * counts["any_cloaking_domain_legacy_scope"] / n if n else 0,
        })
        format_rows.append(row)
    _write_csv(out_dir / "format_pattern_summary.csv", FORMAT_FIELDS, format_rows)

    # CDF inputs that replace the literal, non-reproducible arrays in funcao_cdf.py.
    domain_cdf_rows: list[dict[str, Any]] = []
    groups: dict[str, list[int]] = {
        "all_domains": [], "advertisers_gt_1": [], "advertisers_ge_10": [],
        "advertisers_ge_100": [], "tranco_top_1000": [],
    }
    for row in domain_rows:
        n_links = int(row["link_occurrences"])
        n_owners = int(row["advertisers"])
        groups["all_domains"].append(n_links)
        if n_owners > 1:
            groups["advertisers_gt_1"].append(n_links)
        if n_owners >= 10:
            groups["advertisers_ge_10"].append(n_links)
        if n_owners >= 100:
            groups["advertisers_ge_100"].append(n_links)
        if row["tranco_rank"] not in ("", None) and int(row["tranco_rank"]) <= 1000:
            groups["tranco_top_1000"].append(n_links)
    for group_name, counts in groups.items():
        counts = sorted(counts)
        for rank, n_links in enumerate(counts, start=1):
            domain_cdf_rows.append({
                "group": group_name, "domain_rank": rank,
                "n_domains": len(counts), "link_occurrences": n_links,
                "cdf": rank / len(counts) if counts else 0,
            })
    _write_csv(out_dir / "domain_frequency_cdf.csv", ["group", "domain_rank", "n_domains", "link_occurrences", "cdf"], domain_cdf_rows)

    # Write per-ad comparison statistics. Categories are binary presence indicators
    # and rows are ad-level; missing image labels are excluded from image analyses.
    rq3_rows: list[dict[str, Any]] = []
    total_cloaked_by_scope = {
        "url_exact": sum(int(row.get("any_cloaking_url_scope_ads", 0)) for row in format_rows),
        "domain_legacy": sum(int(row.get("any_cloaking_domain_legacy_scope_ads", 0)) for row in format_rows),
    }
    for (scope, feature, category), (positive_cloaked, positive_noncloaked) in sorted(feature_positive.items()):
        eligible = total_ads
        if feature == "image_label":
            eligible = image_eligible_by_scope[scope]
            cloaked_n = image_cloaked_by_scope[scope]
        else:
            cloaked_n = total_cloaked_by_scope[scope]
        positive_total = positive_cloaked + positive_noncloaked
        if feature == "image_label" and positive_total < minimum_positive_cell:
            continue
        rq3_rows.append(_comparison_row(
            scope=scope, feature=feature, category=category,
            eligible_ads=eligible, cloaked_ads=cloaked_n,
            positive_cloaked=positive_cloaked,
            positive_noncloaked=positive_noncloaked,
            min_positive=minimum_positive_cell,
        ))
    # Adjust within each outcome scope; all comparisons are exploratory.
    for scope in ("url_exact", "domain_legacy"):
        scoped = [row for row in rq3_rows if row["outcome_scope"] == scope]
        _benjamini_hochberg(scoped, "p_value_pearson", "p_value_bh_fdr")
    _write_csv(out_dir / "rq3_categorical_comparisons.csv", RQ3_FIELDS, rq3_rows)

    continuous_rows = []
    for (scope, feature, group), moment in sorted(continuous.items()):
        if group == "cloaked":
            other = continuous.get((scope, feature, "noncloaked"), OnlineMoments())
            continuous_rows.append({
                "outcome_scope": scope, "feature": feature,
                "cloaked_n": moment.n, "cloaked_mean": moment.mean if moment.n else "",
                "cloaked_sd": moment.sd if moment.n else "",
                "noncloaked_n": other.n, "noncloaked_mean": other.mean if other.n else "",
                "noncloaked_sd": other.sd if other.n else "",
                "mean_difference": moment.mean - other.mean if moment.n and other.n else "",
            })
    _write_csv(out_dir / "rq3_continuous_descriptives.csv", CONTINUOUS_FIELDS, continuous_rows)

    # An asset-level long table enables validation/dedup checks without exporting
    # the full media bytes or raw ad text.
    image_label_rows = [
        {"media_hash": asset, "labels": "|".join(sorted(labels)), "associated_ads": len(asset_to_ads.get(asset, set()))}
        for asset, labels in sorted(image_labels.get("asset_labels", {}).items())
    ]
    _write_csv(out_dir / "image_label_assets.csv", ["media_hash", "labels", "associated_ads"], image_label_rows)

    total_patterns_by_type = {
        key: sum(int(row.get(key + "_ads", 0)) for row in format_rows)
        for key in format_pattern_keys
    }
    top_domains = domain_rows[:20]
    report_stats = {
        "ads_scanned": total_ads,
        "metadata_parse_errors": parse_errors,
        "ads_with_url": ads_with_url,
        "link_occurrences": link_occurrences,
        "unique_url_ids": len(unique_url_ids),
        "unique_registered_domains": len(domain_stats),
        "ads_with_meta_domain_seed": ads_with_meta_domain,
        "pattern_counts_by_ad_union_within_format": total_patterns_by_type,
        "domain_summary_top_20": top_domains,
        "tranco_domains_loaded": len(tranco_ranks),
        "labelled_ads_matched": ads_with_label,
        "media_asset_links_in_ad_media": n_db_media_ad_links,
        "url_match_methods": dict(url_match_methods),
        "format_rows": format_rows,
        "metadata_field_availability": metadata_availability_rows,
        "image_label_coverage": image_labels.get("diagnostics", {}),
        "sensitive_raw_urls_written": include_sensitive_urls,
    }
    return report_stats


def _update_feature_counts(
    counts: dict[tuple[str, str, str], list[int]],
    scope: str,
    feature: str,
    categories: Sequence[str],
    cloaked: bool,
) -> None:
    for category in sorted({str(value) for value in categories if str(value)}):
        counts[(scope, feature, category)][0 if cloaked else 1] += 1


def write_redirection_outputs(
    out_dir: Path,
    url_results: Mapping[str, Mapping[str, Any]],
    url_summaries: Mapping[str, Mapping[str, Any]],
    legacy_rows: Sequence[Mapping[str, Any]],
    edge_rows: Sequence[Mapping[str, Any]],
    country_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for key, summary in sorted(url_summaries.items(), key=lambda x: x[1].get("url_id", "")):
        rows.append({
            "url_id": summary["url_id"],
            "source_domain": summary["source_domain"],
            "url_scope_status": summary["status"],
            "final_domain_count": len(summary["final_domains"]),
            "final_domains": "|".join(summary["final_domains"]),
            "countries_with_success": "|".join(summary["countries_with_success"]),
            "countries_with_error": "|".join(summary["countries_with_error"]),
            "successful_observations": summary["successful_observations"],
            "error_observations": summary["error_observations"],
            "country_outcomes_differ": summary["country_outcomes_differ"],
            "within_country_variation": summary["within_country_variation"],
        })
    _write_csv(out_dir / "redirection_url_summary.csv", REDIRECT_URL_FIELDS, rows)
    _write_csv(out_dir / "redirection_domain_legacy_summary.csv", [
        "source_domain", "requested_url_count", "legacy_domain_status",
        "distinct_final_domains", "final_domains", "country_outcomes_differ", "url_statuses",
    ], legacy_rows)
    _write_csv(out_dir / "redirection_edges.csv", REDIRECT_EDGE_FIELDS, edge_rows)
    _write_csv(out_dir / "redirection_by_country.csv", ["country", "url_scope_status", "requested_urls"], country_rows)
    status_counts = Counter(row["url_scope_status"] for row in rows)
    divergent_urls = sum(bool(row["country_outcomes_differ"]) for row in rows)
    within_country_varied = sum(bool(row["within_country_variation"]) for row in rows)
    country_summary = {
        "requested_url_records": len(rows),
        "status_counts": dict(status_counts),
        "country_outcome_divergence_urls": divergent_urls,
        "within_country_multi_destination_urls": within_country_varied,
        "legacy_source_domains": len(legacy_rows),
        "edges": len(edge_rows),
    }
    return country_summary


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def write_report(
    path: Path,
    *,
    redirection_diagnostics: Mapping[str, Any],
    redirection_summary: Mapping[str, Any],
    db_summary: Mapping[str, Any] | None,
    image_label_diagnostics: Mapping[str, Any],
    warnings: Sequence[str],
) -> None:
    lines = [
        "# Analysis run report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "## Input coverage",
        "",
        f"- Registered-domain parser: {redirection_diagnostics.get('domain_parser', 'n/a')}.",
        f"- Redirection source URL union/intersection: {redirection_diagnostics.get('canonical_requested_urls_union', 0):,} / {redirection_diagnostics.get('canonical_requested_urls_intersection', 0):,}.",
        f"- Probe key sets identical: {redirection_diagnostics.get('source_url_key_sets_match', False)}.",
        f"- Probe URL records analyzed: {redirection_summary.get('requested_url_records', 0):,}.",
        "",
        "The repository does not contain the full ad database or the 320k-image label file. "
        "If this run had no ``--db`` input, its domain counts describe only URLs in the probe set, "
        "not the 407,771-ad collection.",
        "",
        "## Redirection outcomes",
        "",
        "Destination-count classes below describe observed final registered domains. They are not "
        "HTTP redirect-hop counts and do not, by themselves, prove reviewer-versus-user cloaking.",
        "",
    ]
    status_rows = [[key, value] for key, value in sorted(redirection_summary.get("status_counts", {}).items())]
    lines.append(_markdown_table(["URL-level outcome", "Requested URLs"], status_rows or [["No probe data", 0]]))
    lines.extend([
        "",
        f"- URLs whose successful country-level destination sets differ: {redirection_summary.get('country_outcome_divergence_urls', 0):,}.",
        f"- URLs with multiple final domains observed within at least one country file: {redirection_summary.get('within_country_multi_destination_urls', 0):,}.",
        "",
    ])

    if db_summary:
        lines.extend(["## Ad and URL characterization", ""])
        lines.extend([
            f"- Ads scanned: {db_summary.get('ads_scanned', 0):,}; metadata parse failures: {db_summary.get('metadata_parse_errors', 0):,}.",
            f"- Ads with at least one parseable link URL: {db_summary.get('ads_with_url', 0):,}.",
            f"- Link occurrences: {db_summary.get('link_occurrences', 0):,}; unique URL hashes: {db_summary.get('unique_url_ids', 0):,}; unique registered domains: {db_summary.get('unique_registered_domains', 0):,}.",
            f"- Ads linking to at least one seed-list Meta domain: {db_summary.get('ads_with_meta_domain_seed', 0):,}.",
            "",
            "### Candidate-pattern rates by display format",
            "",
        ])
        fmt_rows = []
        for row in db_summary.get("format_rows", []):
            fmt_rows.append([
                row["display_format"], row["ads"], row["url_masking_candidate_ads"],
                row["card_domain_heterogeneity_candidate_ads"],
                row["single_external_destination_url_ads"],
                row["multiple_destinations_url_candidate_ads"],
                row["any_cloaking_url_scope_ads"],
                f"{row['any_cloaking_url_scope_rate_pct']:.2f}%",
            ])
        lines.append(_markdown_table(
            ["Format", "Ads", "Caption mismatch", "Card-domain heterogeneity", "One external destination (descriptive)", "Multiple destinations", "Union (URL scope)", "Union rate"],
            fmt_rows,
        ))
        patterns = db_summary.get("pattern_counts_by_ad_union_within_format", {})
        lines.extend([
            "",
            "Pattern counts are ad-level flags and can overlap. Card-domain heterogeneity and URL mismatches are observable proxies, not automatic proof of deceptive intent. The ``domain_legacy`` redirect scope aggregates different requested URLs under the same registrable domain and can over-attribute outcomes; compare it with the exact-URL scope before retaining prior table totals.",
            "",
            "### RQ3 metadata field availability",
            "",
            "Coverage below is measured on successfully parsed ad rows in this input database. Empty coverage means the field was not populated in the analyzed snapshot, not that the field is universally unavailable in Meta data.",
            "",
        ])
        metadata_rows = []
        for item in db_summary.get("metadata_field_availability", []):
            metadata_rows.append([
                item["field"],
                f"{item['non_missing_ads']:,}/{item['ads_scanned']:,}",
                f"{item['availability_pct']:.1f}%",
                item["distinct_values_observed"],
                item["top_values"],
            ])
        lines.append(_markdown_table(
            ["Field", "Non-missing / scanned", "Availability", "Distinct values", "Top values (ad counts)"],
            metadata_rows,
        ))
        lines.extend([
            "",
            "Start/end values are exported verbatim. ``active_lifetime_days`` is derived only when both can be parsed and the end is not before the start; ``total_active_time`` is preserved as raw because its source unit is not established here.",
            "",
            "### RQ3 image-label coverage",
            "",
            f"- Label rows: {image_label_diagnostics.get('rows', 0):,}; unique labelled asset IDs: {image_label_diagnostics.get('labelled_assets', 0):,}; matched assets: {image_label_diagnostics.get('matched_assets', 0):,}; unmatched assets: {image_label_diagnostics.get('unmatched_assets', 0):,}; direct ad-level labels: {image_label_diagnostics.get('direct_labelled_ads', 0):,}; ads with labels attached: {db_summary.get('labelled_ads_matched', 0):,}.",
            "- Image-label comparisons use ads with at least one attached label. Unlabeled ads are treated as missing, never as negative examples.",
            "",
        ])
    else:
        lines.extend([
            "## Ad-level analysis not run",
            "",
            "Pass the full SQLite advert database with ``--db`` to generate per-ad URL, display-format, masking, and RQ3 comparison files. Pass image labels with ``--image-labels`` to include the visual-content analysis.",
            "",
        ])

    if warnings:
        lines.extend(["## Warnings / checks to resolve", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    lines.extend([
        "## Interpretation guardrails",
        "",
        "1. Report ads, link occurrences, exact URLs, and registered domains as distinct units.",
        "2. Report the union of flagged ads separately from per-pattern counts; the latter overlap.",
        "3. Treat location/repetition-dependent destinations as observed conditional variation, not direct proof of a platform-review/user split.",
        "4. The raw URLs in the input can contain phone numbers, signed tokens, and tracking parameters. Output CSVs omit query strings and raw captions unless ``--include-sensitive-urls`` is explicitly supplied.",
        "5. RQ3 estimates are descriptive associations; clustered/adjusted models and manual validation are still required for a paper-level claim.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def _make_plots(out_dir: Path, db_summary: Mapping[str, Any] | None) -> list[str]:
    """Create compact paper-facing PNGs when matplotlib is installed."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return ["matplotlib is not installed; skipped plots"]

    warnings: list[str] = []
    plot_dir = out_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    domain_file = out_dir / "domain_summary.csv"
    if domain_file.exists():
        with domain_file.open(newline="", encoding="utf-8") as stream:
            domains = list(csv.DictReader(stream))
        top = domains[:20]
        if top:
            fig, ax = plt.subplots(figsize=(9, 7))
            labels = [row["domain"] for row in reversed(top)]
            values = [int(row["link_occurrences"]) for row in reversed(top)]
            ax.barh(labels, values, color="#2a6f97")
            ax.set_xscale("log")
            ax.set_xlabel("Link occurrences (log scale)")
            ax.set_title("Most frequently linked registrable domains")
            fig.tight_layout()
            fig.savefig(plot_dir / "rq1_top_domains.png", dpi=180)
            plt.close(fig)

        if domains:
            fig, ax = plt.subplots(figsize=(8, 5))
            for name, predicate in (
                ("All domains", lambda r: True),
                (">1 advertiser", lambda r: int(r["advertisers"]) > 1),
                ("≥10 advertisers", lambda r: int(r["advertisers"]) >= 10),
                ("≥100 advertisers", lambda r: int(r["advertisers"]) >= 100),
            ):
                counts = sorted(int(row["link_occurrences"]) for row in domains if predicate(row))
                if counts:
                    ys = [(i + 1) / len(counts) for i in range(len(counts))]
                    ax.step(counts, ys, where="post", label=name)
            tranco = sorted(
                int(row["link_occurrences"]) for row in domains
                if row.get("tranco_rank", "") and int(row["tranco_rank"]) <= 1000
            )
            if tranco:
                ax.step(tranco, [(i + 1) / len(tranco) for i in range(len(tranco))], where="post", label="Tranco top 1k in sample")
            ax.set_xscale("log")
            ax.set_xlabel("Link occurrences per domain (log scale)")
            ax.set_ylabel("Empirical CDF")
            ax.set_ylim(0, 1.02)
            ax.grid(axis="both", alpha=0.2)
            ax.legend(frameon=False)
            ax.set_title("Concentration of URL destinations")
            fig.tight_layout()
            fig.savefig(plot_dir / "rq1_domain_frequency_cdf.png", dpi=180)
            plt.close(fig)

    tld_strata_file = out_dir / "tld_by_advertiser_stratum.csv"
    if tld_strata_file.exists():
        with tld_strata_file.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        strata = ["1", "2-10", "11-100", "101-1000", ">1000"]
        suffixes = [s for s, _ in Counter({r["public_suffix"]: 1 for r in rows}).most_common(8)]
        if rows and suffixes:
            fig, ax = plt.subplots(figsize=(11, 6))
            width = 0.35
            x = list(range(len(strata)))
            for offset, metric, label in ((-width / 2, "share_domains_pct", "Unique-domain share"), (width / 2, "share_advertiser_weight_pct", "Advertiser-weighted share")):
                bottoms = [0.0] * len(strata)
                for suffix in suffixes:
                    values = []
                    for stratum in strata:
                        row = next((r for r in rows if r["advertiser_stratum"] == stratum and r["public_suffix"] == suffix), None)
                        values.append(float(row[metric]) if row else 0.0)
                    ax.bar([value + offset for value in x], values, width, bottom=bottoms, label=suffix if offset == -width / 2 else None)
                    bottoms = [a + b for a, b in zip(bottoms, values)]
            ax.set_xticks(x, strata)
            ax.set_ylabel("Share within advertiser stratum (%)")
            ax.set_xlabel("Number of distinct advertisers using a domain")
            ax.set_title("Public-suffix mix: unique domains vs advertiser-weighted")
            ax.legend(title="Public suffix", bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False)
            fig.tight_layout()
            fig.savefig(plot_dir / "rq1_tld_by_advertiser_stratum.png", dpi=180)
            plt.close(fig)

    fmt_file = out_dir / "format_pattern_summary.csv"
    if fmt_file.exists():
        with fmt_file.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        rows = sorted(rows, key=lambda r: float(r["any_cloaking_url_scope_rate_pct"]), reverse=True)
        if rows:
            fig, ax = plt.subplots(figsize=(9, 5))
            labels = [row["display_format"] for row in reversed(rows)]
            vals = [float(row["any_cloaking_url_scope_rate_pct"]) for row in reversed(rows)]
            ax.barh(labels, vals, color="#e76f51")
            ax.set_xlabel("Ads with ≥1 candidate signal (%)")
            ax.set_title("Candidate-signal union by display format (URL-exact scope)")
            fig.tight_layout()
            fig.savefig(plot_dir / "rq2_format_prevalence.png", dpi=180)
            plt.close(fig)

    rq3_file = out_dir / "rq3_categorical_comparisons.csv"
    if rq3_file.exists():
        with rq3_file.open(newline="", encoding="utf-8") as stream:
            rows = [row for row in csv.DictReader(stream) if row.get("feature") == "image_label" and row.get("outcome_scope") == "url_exact"]
        rows.sort(key=lambda r: abs(float(r["risk_difference_pp"])), reverse=True)
        rows = rows[:20]
        if rows:
            fig, ax = plt.subplots(figsize=(10, max(5, 0.34 * len(rows))))
            labels = [row["category"] for row in reversed(rows)]
            effects = [float(row["risk_difference_pp"]) for row in reversed(rows)]
            low = [float(row["risk_difference_95_low_pp"]) for row in reversed(rows)]
            high = [float(row["risk_difference_95_high_pp"]) for row in reversed(rows)]
            errors = [[max(0.0, e - l) for e, l in zip(effects, low)], [max(0.0, h - e) for e, h in zip(effects, high)]]
            ax.errorbar(effects, list(range(len(rows))), xerr=errors, fmt="o", color="#264653", ecolor="#8d99ae", capsize=2)
            ax.axvline(0, color="#777777", linewidth=1, linestyle="--")
            ax.set_yticks(range(len(rows)), labels)
            ax.set_xlabel("Cloaked − non-cloaked prevalence (percentage points)")
            ax.set_title("Exploratory image-label associations (95% Wald CI)")
            fig.tight_layout()
            fig.savefig(plot_dir / "rq3_image_label_risk_differences.png", dpi=180)
            plt.close(fig)

    edge_file = out_dir / "redirection_edges.csv"
    if edge_file.exists():
        with edge_file.open(newline="", encoding="utf-8") as stream:
            edges = list(csv.DictReader(stream))
        edges.sort(key=lambda r: int(r["requested_urls"]), reverse=True)
        edges = edges[:20]
        if edges:
            fig, ax = plt.subplots(figsize=(11, max(5, 0.34 * len(edges))))
            labels = [f"{row['source_domain']} → {row['destination_domain']} ({row['country']})" for row in reversed(edges)]
            counts = [int(row["requested_urls"]) for row in reversed(edges)]
            ax.barh(labels, counts, color="#457b9d")
            ax.set_xlabel("Requested URLs with this observed source–destination pair")
            ax.set_title("Most frequent observed final-domain flows")
            fig.tight_layout()
            fig.savefig(plot_dir / "rq2_top_redirect_flows.png", dpi=180)
            plt.close(fig)

    return warnings


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="SQLite database with advert metadata (optional for probe-only run)")
    parser.add_argument("--redirections", type=Path, default=DEFAULT_REDIRECTIONS, help="folder of per-country redirect-result JSONs")
    parser.add_argument("--image-labels", type=Path, help="image label CSV/JSON/JSONL or extract_media.py results SQLite DB")
    parser.add_argument("--label-column", default="auto", help="image label field name (default: auto-detect)")
    parser.add_argument("--label-id-column", default="auto", help="label-file identifier column; for image labels it must match ad_media.hash unless the file already contains ad_archive_id")
    parser.add_argument("--label-model", default=None, help="optional model filter for a results SQLite DB")
    parser.add_argument("--min-confidence", type=float, default=None, help="optional confidence threshold if a score column exists")
    parser.add_argument("--tranco", type=Path, help="optional Tranco list CSV (rank,domain or domain,rank)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output folder (default: {DEFAULT_OUT})")
    parser.add_argument("--limit", type=int, default=None, help="debug: scan only first N ads")
    parser.add_argument("--min-positive-cell", type=int, default=20, help="minimum total positive ads to include an image-label comparison")
    parser.add_argument("--include-sensitive-urls", action="store_true", help="include raw link URLs/captions in url_inventory.csv (contains query values and may be sensitive)")
    parser.add_argument("--plots", action="store_true", help="write optional PNG visualizations (requires matplotlib)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be positive")
    if args.min_positive_cell < 1:
        raise SystemExit("--min-positive-cell must be positive")
    if args.min_confidence is not None and not 0 <= args.min_confidence <= 1:
        raise SystemExit("--min-confidence must be between 0 and 1")

    started = time.time()
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    url_results, redirect_diagnostics = load_redirection_results(args.redirections)
    url_summaries, legacy_domain_status, edge_rows, country_rows, legacy_rows = summarize_redirections(url_results)
    redirection_summary = write_redirection_outputs(
        out_dir, url_results, url_summaries, legacy_rows, edge_rows, country_rows
    )
    warnings = list(redirect_diagnostics.get("warnings", []))
    if _TLDEXTRACT is None:
        warnings.append("tldextract is not installed; public-suffix analysis uses the documented limited fallback")

    db_summary: dict[str, Any] | None = None
    image_label_data: dict[str, Any] = load_image_labels(None, {})
    if args.image_labels and not args.db:
        image_label_data["diagnostics"]["input"] = args.image_labels.name
        warnings.append("Image labels were not read or joined because --db was not supplied")

    if args.db:
        # First read the ad/media bridge from the main DB, then load image labels
        # using that bridge. The main DB remains read-only throughout.
        db_conn = _read_only_sqlite(args.db)
        try:
            asset_to_ads, _ = load_media_associations(db_conn)
        finally:
            db_conn.close()
        image_label_data = load_image_labels(
            args.image_labels, asset_to_ads, label_column=args.label_column,
            id_column=args.label_id_column,
            model=args.label_model, min_confidence=args.min_confidence,
        ) if args.image_labels else load_image_labels(None, asset_to_ads)
        tranco_ranks = _load_tranco(args.tranco)
        db_summary = analyze_database(
            args.db, out_dir,
            url_results=url_results,
            url_summaries=url_summaries,
            legacy_domain_status=legacy_domain_status,
            image_labels=image_label_data,
            tranco_ranks=tranco_ranks,
            limit=args.limit,
            include_sensitive_urls=args.include_sensitive_urls,
            minimum_positive_cell=args.min_positive_cell,
        )
        warnings.extend(image_label_data.get("diagnostics", {}).get("warnings", []))
        warnings.extend([f"Image-label assets unmatched to ad_media: {image_label_data['diagnostics'].get('unmatched_assets', 0):,}"] if image_label_data.get("diagnostics", {}).get("unmatched_assets", 0) else [])
        warnings.extend([f"Ad metadata rows skipped due to JSON parse errors: {db_summary.get('metadata_parse_errors', 0):,}"] if db_summary.get("metadata_parse_errors", 0) else [])
    else:
        tranco_ranks = _load_tranco(args.tranco)
        # No ad DB: classify source/final domains in the probe subset without
        # representing them as a sample of all ads.
        probe_domain_counts: Counter[str] = Counter()
        for record in url_results.values():
            if record.get("source_domain"):
                probe_domain_counts[record["source_domain"]] += 1
        probe_rows = [{
            "domain": domain, "public_suffix": domain_parts(domain)[1],
            "link_occurrences": count, "distinct_urls": count, "ads": "",
            "advertisers": "", "meta_owned_seed": domain in META_DOMAINS,
            "known_shortener_candidate": domain in SHORTENER_DOMAINS,
            "tranco_rank": tranco_ranks.get(domain, ""),
            "redirect_status_domain_legacy": legacy_domain_status.get(domain, {}).get("status", "not_probed"),
        } for domain, count in sorted(probe_domain_counts.items(), key=lambda x: (-x[1], x[0]))]
        _write_csv(out_dir / "probe_source_domain_summary.csv", DOMAIN_FIELDS, probe_rows)
        if args.limit:
            warnings.append("--limit has no effect without --db")

    if args.plots:
        warnings.extend(_make_plots(out_dir, db_summary))

    write_report(
        out_dir / "report.md",
        redirection_diagnostics=redirect_diagnostics,
        redirection_summary=redirection_summary,
        db_summary=db_summary,
        image_label_diagnostics=image_label_data.get("diagnostics", {}),
        warnings=warnings,
    )
    manifest = {
        "pipeline": "analysis/pipeline.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python_version": sys.version.split()[0],
        "tldextract_version": _TLDEXTRACT_VERSION,
        "elapsed_seconds": round(time.time() - started, 3),
        "inputs": {
            "database": args.db.name if args.db else None,
            "redirections": str(args.redirections) if args.redirections else None,
            "image_labels": args.image_labels.name if args.image_labels else None,
            "tranco": args.tranco.name if args.tranco else None,
        },
        "options": {
            "limit": args.limit,
            "include_sensitive_urls": args.include_sensitive_urls,
            "min_positive_cell": args.min_positive_cell,
            "min_confidence": args.min_confidence,
            "label_column": args.label_column,
            "label_id_column": args.label_id_column,
            "label_model": args.label_model,
            "plots": args.plots,
        },
        "redirection_diagnostics": redirect_diagnostics,
        "redirection_summary": redirection_summary,
        "image_label_diagnostics": image_label_data.get("diagnostics", {}),
        "database_summary": db_summary,
        "warnings": warnings,
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Wrote analysis outputs to {out_dir}")
    print(f"Redirected URL records: {redirection_summary.get('requested_url_records', 0):,}")
    if db_summary:
        print(f"Ads scanned: {db_summary.get('ads_scanned', 0):,}; domains: {db_summary.get('unique_registered_domains', 0):,}")
    if warnings:
        print(f"Warnings: {len(warnings)} (see report.md / run_manifest.json)", file=sys.stderr)
    return 0


def main_guard() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    main_guard()
