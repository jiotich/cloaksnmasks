# Consolidated Meta-ad URL analysis

`pipeline.py` replaces the overlapping exploratory scripts in `analysis/legacy/` with one local, reproducible run for the three paper questions:

1. **RQ1:** characterize ad link URLs and domains;
2. **RQ2:** measure URL-related cloaking candidate signals and observed final-destination variation;
3. **RQ3:** compare candidate-signal ads with other ads using image labels and the metadata actually present.

The pipeline is read-only with respect to inputs. It does not fetch ads, open URLs, make network requests, call a classifier, or modify the source database. Core analysis uses Python’s standard library. Python 3.10+ is required. `tldextract` is strongly recommended for the Public Suffix List (PSL); `matplotlib` is optional for plots.

## Run

Full run (replace the example paths with the actual full ad database and image-label file):

```bash
python analysis/pipeline.py \
  --db /path/to/full_lighsnap.db \
  --redirections data/redirection_results \
  --image-labels /path/to/image_labels.csv \
  --label-id-column media_hash \
  --label-column label \
  --tranco /path/to/tranco.csv \
  --out analysis/output/run-YYYY-MM-DD \
  --plots
```

A redirection-only coverage run works with this repository’s checked-in files:

```bash
python analysis/pipeline.py \
  --redirections data/redirection_results \
  --out analysis/output/probe-audit
```

The default output directory is `analysis/output/latest/`, which is excluded from Git. Use a dated `--out` directory to retain separate runs locally. The manifest records input basenames, options, runtime, parser, coverage diagnostics, and warnings. A run with no `--db` does **not** analyze or represent the full ad corpus.

Recommended for publication-grade domain statistics:

```bash
python -m pip install tldextract
```

`tldextract` is configured to use its bundled PSL snapshot (no runtime URL fetch); the package version is recorded in `run_manifest.json`. If it is unavailable, the script warns and falls back to a deliberately limited built-in suffix list. Do not use fallback-derived public-suffix results in a paper without validation. To create PNG figures, also install `matplotlib`.

### Useful options

- `--limit N`: debug-only scan of the first N SQLite rows; the query has no ordering guarantee. Never use a limited run for paper statistics.
- `--label-id-column NAME`: specify the image/classification file’s identifier field. For media-level labels, its values must equal `ad_media.hash`; a custom column name does not change the join key.
- `--label-column NAME`: specify the category/label field; defaults to automatic detection.
- `--label-model NAME`: filter a results SQLite input to one model.
- `--min-confidence FLOAT`: apply a threshold if the label file has a `confidence`, `score`, or `probability` column. Rows without a score are not filtered.
- `--min-positive-cell N`: omit image-label comparisons with fewer than N positive ads; defaults to 20. This filters rare **image-label** rows, not other categorical features.
- `--include-sensitive-urls`: include raw link URLs and captions in `url_inventory.csv`. This can expose query parameters, identifiers, phone numbers, tracking tokens, or other sensitive values; off by default.
- `--plots`: create optional paper-facing PNGs, requiring `matplotlib`.

## Input contracts

### Ad SQLite database

The pipeline expects an `advert` table with a metadata JSON/text column and preferably these columns:

```text
advert(ad_archive_id, advertiser_id, display_format, metadata, ...)
```

`metadata` must decode to an object. The link parser reads `metadata.snapshot`, including `link_url`, `caption`, `link_description`, `display_format`, `cta_type`, `page_categories`, `page_entity_type`, `cards`, `body`, and `title` when present. `publisher_platform`, `start_date`, `end_date`, and `total_active_time` are sought at the metadata top level; categories/entity fields also have the documented snapshot fallbacks. Missing fields remain missing and are counted.

For image joins, the legacy AdverEyes schema is:

```text
ad_media(hash, ad_archive_id, url_filename, ...)
```

The expected media join is `image_labels.media_hash`/`hash` → `ad_media.hash` → `ad_media.ad_archive_id` → `advert.ad_archive_id`. The image hash must match exactly. The code can also accept labels already aggregated to `ad_archive_id`/`ad_id`. It does not infer a join from visual similarity or filenames.

### Image classifications

Accepted input formats:

- CSV or TSV, one row per asset/label (common fields: `media_hash`, `hash`, `image_hash`, `asset_hash`, `label`, `labels`, `category`, `classification`, `response`);
- JSON list/object or JSONL/NDJSON with equivalent fields;
- SQLite with a `results` table containing `hash` plus `response`/`label`; the legacy `extract_media.py` output also supports `model`, `error`, and `format` columns.

A classification may be a scalar label, a list/JSON object with `label`, `labels`, `category`, or `categories`, or an explicit pipe/semicolon-separated list. Free-form prose is treated as one label rather than split on commas. Check the classifier’s label taxonomy and normalize it before making substantive comparisons. If the SQLite `format` field is present, non-image formats are excluded; a file with no media type is assumed to contain image classifications because the schema alone cannot prove the asset type.

Rows with an error or no usable label do not create a negative example. Labels are de-duplicated per asset, then aggregated to ad-level presence through `ad_media`. The output reports distinct labeled assets, matched/unmatched assets, and ads with attached labels. Image-level and ad-level coverage are different quantities. If an asset maps to multiple ads, its label is associated with each linked ad; duplicated creative assets can therefore make ad observations dependent.

### Redirect results and Tranco

`--redirections` is a directory containing per-country JSON objects. Each non-`metadata` key is an input/requested URL and each value is a list (or scalar) of observed final URL strings. Values such as `Errored out`, `timeout`, and `failed` are counted as errors rather than domains. `metadata.total`, `metadata.errors`, and `metadata.completed` are retained as diagnostics and are not treated as per-request success guarantees.

The files in this checkout are named `alemanha.json`, `brasil.json`, `eua.json`, and `portugal.json`. Their canonical requested-URL key sets match at 26,278 keys. The pipeline preserves path and query when matching an ad URL to a probe key, normalizes scheme/host case and `www`, and removes fragments. A short SHA-256 ID is written in place of a raw URL in default output.

A Tranco input should be a CSV with either `rank,domain` or `domain,rank` columns, with or without a header. The list’s release date and version should be recorded in the paper/release materials.

## Measurement definitions

### RQ1

- `link_occurrences`: one count per parseable ad/card link instance. Repeated cards/links may count more than once.
- `unique_url_ids`: unique canonical URLs, represented by short SHA-256 IDs in outputs.
- `unique_registered_domains`: unique registered domains/eTLD+1s under the active parser.
- In `domain_summary.csv`, `ads` is the number of unique ad IDs linking to the domain; `advertisers` is the number of unique non-empty owner IDs.
- In `tld_summary.csv`, `ad_domain_occurrences` is the sum of per-domain ad counts within a suffix. An ad linking to two domains under the same suffix contributes twice. It is not a unique-ad count.
- CDF curves use **link occurrences per domain**. Advertiser strata use the number of distinct owners observed per domain; a missing owner ID is assigned the `unknown` stratum.
- The Tranco rank is an external popularity reference, not a maliciousness/reputation label.

### RQ2

- **Caption/link mismatch candidate:** compare a URL-like domain extracted from a caption with the registered domain of its embedded link. If the caption contains no parseable URL-like hostname, it is not counted as a mismatch.
- **Card-domain heterogeneity candidate:** for DCO/DPA/CAROUSEL or an ad with cards, more than one distinct linked registered domain appears among the parsed card links.
- **Single external destination:** an exact requested URL has one observed final registered domain different from the source. This is descriptive and **not** a cloaking signal by itself.
- **Multiple destination domains:** an exact requested URL has more than one distinct observed final registered domain across its successful probe outcomes. This is retained as a conditional-destination candidate, not proof of deceptive delivery. `country_outcomes_differ` compares successful destination sets in at least two countries; `within_country_variation` records multiple final domains within a country file.
- **Primary ad-level URL-exact union:** mismatch OR card-domain heterogeneity OR multiple exact-URL destination domains. Flags are deduplicated per ad. Single external destinations are excluded.
- **Legacy domain scope:** different requested URLs are grouped under one source registered domain. This can attribute another URL’s result to a link that was not probed and is reported only as a sensitivity analysis.

Neither different final domains nor probe multiplicity is an HTTP-hop count. If geographies differ, localization, A/B tests, affiliate routing, access instability, and other benign explanations remain possible. The current JSON data do not establish what Meta’s reviewers saw.

### RQ3

- Categorical contrasts are ad-level category-presence comparisons. Platform, category, and image labels may be multi-valued; an ad can therefore appear in more than one category row.
- Non-image metadata feature rows use all successfully parsed ads as eligible; image-label rows use only ads with at least one attached image label. Unlabeled ads are excluded from the image-label denominator.
- The comparison is between the URL-exact primary union and its complement, with a separate `domain_legacy` sensitivity scope.
- The output includes prevalence rates, risk differences (percentage points) with Wald 95% intervals, odds ratios (with a 0.5 continuity correction for effect-size calculations), uncorrected Pearson chi-square p-values, and BH-adjusted p-values within each outcome scope. These are descriptive/unadjusted; repeated advertisers, duplicated assets, and campaigns can violate independence.
- Continuous outputs give group means and sample SDs. `active_lifetime_days` is only included for rows with two parsable, chronologically consistent dates. `total_active_time` is preserved raw; no unit is inferred.

## Outputs

Every run writes:

- `report.md` — input coverage, redirection outcome counts, ad/format summary when a DB is supplied, metadata-field coverage, label coverage, warnings, and interpretation guardrails.
- `run_manifest.json` — run timestamp, inputs/options, software/parser details, diagnostics, summary counts, and warnings.
- `redirection_url_summary.csv` — one row per canonical requested URL, hashed ID, source/final domains, error counts, and country-variation flags; no raw query strings.
- `redirection_domain_legacy_summary.csv` — source-domain aggregation for sensitivity analysis.
- `redirection_edges.csv` — source → observed final registered domain, country, and requested-URL count; these are not intermediate hops.
- `redirection_by_country.csv` — per-country URL outcome counts.

With `--db`, it also writes:

- `ad_inventory.csv` — one row per successfully parsed ad, selected metadata, date values, link and media counts, RQ2 flags, and attached image labels.
- `url_inventory.csv` — one row per parseable link/card URL. Raw URL/caption values are omitted unless `--include-sensitive-urls` is set.
- `domain_summary.csv`, `tld_summary.csv`, `tld_by_advertiser_stratum.csv`, `domain_frequency_cdf.csv` — RQ1 domain outputs.
- `format_pattern_summary.csv` — ad-level candidate counts/rates by format; component counts overlap.
- `mask_edges.csv`, `mask_domain_summary.csv` — caption-domain to embedded-domain mismatch summaries.
- `metadata_field_availability.csv` — actual field coverage and top categorical values for the scanned DB snapshot.
- `rq3_categorical_comparisons.csv`, `rq3_continuous_descriptives.csv` — RQ3 contrasts and descriptives.
- `image_label_assets.csv` — one row per labeled media hash with categories and associated-ad count; no image bytes.

With `--plots` and `matplotlib`, PNGs are written to `plots/`. Outputs contain ad/owner IDs and domain-level information; review the institution’s data-handling requirements before sharing them.

## Reproducibility checks

Run the standard-library integration tests:

```bash
python -m unittest discover -s analysis/tests -v
```

The tests build a temporary SQLite database, synthetic country probes, and image-label CSV. They verify matching, error handling, card/mismatch signals, media joins, metadata availability, lifetime derivation, and generated output files. They do not substitute for checking the full input database, label taxonomy, sampling process, or human validation.
