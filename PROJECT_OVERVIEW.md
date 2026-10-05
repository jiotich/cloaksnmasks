# Project overview: *Behind Cloaks and Masks*

## Recommended focus

Reformulate the paper as a study of **URLs embedded in Meta ads**: first characterize the link ecosystem, then measure URL-related cloaking candidates, then compare those ads with the rest of the sample using the available image classifications and ad metadata. The novelty is narrow and empirical: the platform, unit of analysis, URL/creative linkage, and sample—not cloaking or online-ad security in general.

### Research questions

1. **RQ1 — URL characterization.** How are destination URLs in the collected Meta ads structured and distributed across domains, public suffixes, advertisers, and ad formats?
2. **RQ2 — URL cloaking signals.** What observable URL-related cloaking signals occur in the sample, and how prevalent are they? Which signals are visible in ad metadata, and which require the available destination probes?
3. **RQ3 — Cloaked versus non-cloaked ads.** How do ads with at least one RQ2 candidate signal differ from other ads in image-label categories and in the ad metadata actually available—publisher platform, page/advertiser categories, page entity type, CTA, and active dates/lifetime?

Use the word **candidate** throughout the measurement description unless a signal has been manually validated or directly demonstrates conditional delivery. “Cloaked” can remain in the RQ wording as the motivating construct, but the results must distinguish observed URL properties from deceptive intent and from a reviewer-versus-user split view.

## Positioning and contribution claims

The current paper draft overreaches when it calls the work “first of its kind,” proposes a unified definition spanning more than 20 years, or presents every redirect, caption mismatch, and card-domain difference as malicious. Earlier work studied web/search-engine cloaking at WWW, cloaking affecting Google Search and Google Ads, and ad-based URL-shortening services at WWW. Meta/Facebook ads have also been studied in WWW, NDSS, USENIX Security, FAccT, and ICWSM—but principally through political-ad auditing, ad-library transparency, targeting/delivery, content, or particular harmful-ad ecosystems.

A defensible contribution statement is therefore:

> We provide a large-scale, Meta-ad-focused characterization of embedded destination URLs; operationalize several observable URL-related risk signals without equating them with proven deception; and, subject to the final join and field-coverage audit, relate those signals to image classifications and the ad metadata present in the collection.

Do **not** claim that this is the first study of ad cloaking, URL cloaking, or Meta advertising. A targeted literature search found clear prior work in each adjacent area; the exact novelty claim still needs a systematic search before submission. In particular, Invernizzi et al. studied cloaking in Google Search and Google Ads, so novelty must be scoped to the Meta-ad data and analysis rather than advertising generally.

### Selected literature to anchor the review

- **General web cloaking:** Wu and Davison, “Detecting Semantic Cloaking on the Web,” WWW 2006, [doi:10.1145/1135777.1135901](https://doi.org/10.1145/1135777.1135901).
- **Cloaking in search and ads:** Invernizzi et al., “Cloak of Visibility: Detecting When Machines Browse a Different Web,” IEEE S&P 2016, [Google Research record](https://research.google/pubs/pub45365/). This is essential prior art; it studies Google Search and Google Ads, not Meta ads.
- **Ad-based shorteners:** Nikiforakis et al., “Stranger Danger: Exploring the Ecosystem of Ad-Based URL Shortening Services,” WWW 2014, [doi:10.1145/2566486.2567983](https://doi.org/10.1145/2566486.2567983).
- **Facebook ad ecosystem and auditing:** Andreou et al., “Measuring the Facebook Advertising Ecosystem,” NDSS 2019, [doi:10.14722/ndss.2019.23280](https://doi.org/10.14722/ndss.2019.23280); Silva et al., “Facebook Ads Monitor,” WWW 2020, [doi:10.1145/3366423.3380109](https://doi.org/10.1145/3366423.3380109); and Edelson, Lauinger, and McCoy, “A Security Analysis of the Facebook Ad Library,” IEEE S&P 2020, [doi:10.1109/SP40000.2020.00084](https://doi.org/10.1109/SP40000.2020.00084).
- **Problematic ads and Meta delivery:** Ali et al., “Problematic Advertising and its Disparate Exposure on Facebook,” USENIX Security 2023, [arXiv:2306.06052](https://arxiv.org/abs/2306.06052); Aisenpreis et al., “How Do US Congress Members Advertise Climate Change?,” ICWSM 2023, [doi:10.1609/icwsm.v17i1.22121](https://doi.org/10.1609/icwsm.v17i1.22121); and Jain and Wood, “Facebook Political Ads and Accountability,” ICWSM 2024, [doi:10.1609/icwsm.v18i1.31346](https://doi.org/10.1609/icwsm.v18i1.31346).
- **Brazilian transparency context:** Santini et al., “Seeing through Opacity: The Limitations of Digital Ad Transparency in Brazil,” FAccT 2024, [doi:10.1145/3630106.3659034](https://doi.org/10.1145/3630106.3659034).
- **Adjacent online-ad fraud:** Papadogiannakis et al., “Welcome to the Dark Side: Analyzing the Revenue Flows of Fraud in the Online Ad Ecosystem,” WWW 2025, [doi:10.1145/3696410.3714899](https://doi.org/10.1145/3696410.3714899). It is not a Meta Ad Library study, but informs the broader advertising-fraud context.

Use these works to establish what has already been studied; do not imply that they use the same population or detect the same behavior. The ICWSM strand is useful for situating the Meta-ad dataset and the RQ3 content comparison, while WWW/security work anchors URL and cloaking methodology.

## Operational scope and interpretation

| Observable measure | Pipeline definition | What it does **not** establish |
|---|---|---|
| URL/domain characterization | Parse each web link from the ad snapshot/cards; characterize URL path/query presence, registered domain, public suffix, ad format, advertiser/page, and destination concentration. Report link occurrences, unique URLs, ads, advertisers, and domains as separate units. | A domain count is not an ad count; a public-suffix distribution is not a safety classifier. |
| Caption-versus-link mismatch | A URL-like hostname is extracted from the caption and compared with the registrable domain of `link_url`. | A mismatch alone is not proof of phishing or malicious intent; the caption may be generic, abbreviated, localized, or a tracking/affiliate presentation. |
| Card-domain heterogeneity | A card-format ad has links to more than one registered domain. | A heterogeneous carousel/DPA/DCO destination set can be legitimate. It is a review candidate, not proof that a harmless card hides a malicious one. |
| Exact-URL destination variation | For the same normalized requested URL, count distinct observed final registered domains across the supplied country/repeated-probe results. Preserve error observations separately. | A final-domain set is not an HTTP hop count. Geographic variation can reflect localization, A/B testing, affiliate logic, or infrastructure changes; it does not alone prove a Meta-review/user split. |
| One external final domain | Descriptive probe outcome when one observed final registered domain differs from the source domain. | This is **not** counted as cloaking by itself. Ordinary tracking and short-link redirects commonly end on another domain. |
| Legacy domain-level outcome | Sensitivity analysis groups different requested URLs by source registered domain. | It can attribute another path’s outcome to an ad URL that was never probed. Keep separate from the primary exact-URL scope. |

A positive RQ2 union should be computed at the **ad level** and deduplicated across its component candidate flags. The pipeline’s primary union includes caption/link mismatches, card-domain heterogeneity, and multiple-final-domain variation for an exact probed URL; a single external destination is reported descriptively but excluded from the union. Domain-aggregated results are a legacy sensitivity scope. All signal counts overlap and must not be summed as a unique-ad count.

The probe JSONs contain final URL observations and per-request error markers. Treat the four file-level `metadata` objects as bookkeeping, not as a guarantee that every request succeeded. No hop-by-hop chain should be inferred unless such data are separately supplied. A geolocation probe is not a reviewer-versus-user experiment; that claim would require the appropriate controlled profiles and evidence.

## Data and current evidentiary status

### What is present in this checkout

- The six-page manuscript PDF and reconstructed LaTeX sections/tables are under `paper/`.
- Four country probe JSON files are in `data/redirection_results/`. The four files have the same 26,278 requested-URL keys. A probe-only run of the consolidated pipeline reports 26,278 URL records; 588 with multiple observed final registered domains, 22,357 resolving to the source registered domain, 390 with one external final domain, and 2,943 unresolved. It observed different successful destination sets across countries for 572 URLs and more than one final domain within at least one country file for 521 URLs. These are **probe-sample diagnostics only**, not full-ad-set prevalence. The run used the pipeline’s limited suffix fallback because `tldextract` is not installed; rerun with the PSL-backed parser before using any domain-level number in a paper.
- The recovered `source_visualizations.ipynb` accesses `publisher_platform`, `start_date`, `end_date`, `total_active_time`, and, inside `snapshot`, `cta_type`, `page_categories`, and `page_entity_type`. This documents fields the older notebook attempted to analyze; it does **not** establish their non-missing coverage in the current full database.
- The old AdverEyes SQLite schema defines `ad_media(hash, ad_archive_id, ...)`, which is the expected image-hash-to-ad join.

### What is absent

The full ad SQLite database and the user’s 320k image-classification file/schema are not in this repository. Consequently, no full-corpus RQ1/RQ2 prevalence, RQ3 image-label comparison, or actual metadata-availability rate has been computed in this checkout. The pipeline is ready to inspect those inputs and writes `metadata_field_availability.csv` and the image-join coverage to `report.md`/`run_manifest.json` once supplied.

### Manuscript figures/counts to revalidate before reuse

The draft reports a Brazil-focused collection from April 20 to June 19, 2026, **407,771 ads**, and over 600 GB. These remain draft-reported values until the database is rerun and collection/deduplication units are documented. The table lists URL masking 19,470; card cloaking 929; multiple redirection 8,322; single redirection 7,490; and a reported union of 26,921 ads (6.6%). Per-pattern counts overlap; do not add them to obtain a unique-ad total.

The table/text also has arithmetic/rounding inconsistencies: VIDEO + IMAGE is about 82.4%, not 81.1%; DCO + CAROUSEL + DPA is about 16.8%, not 16.6%; VIDEO rounds to 54.7% at one decimal; MULTI_IMAGES (3,153) and DPA (2,453) are not `<0.1%`. The paper says 26,279 unique domains while the probe JSONs have 26,278 requested URL keys; clarify the different units/populations. The old `result_bp.tex` contains other totals (for example, 24,213 URL masks and a different unique union) and is stale until a single ad-level recomputation reconciles it.

## RQ3 metadata and image-label plan

The pipeline checks actual values in successfully parsed rows and reports, for each field, non-missing count, missing count, coverage, distinct-value count (where meaningful), and common values. It does not assume that a field exists or is complete.

| Requested comparison | Input field/path | Treatment |
|---|---|---|
| Publisher platform | `metadata.publisher_platform` | One ad-level indicator per listed platform; report missing coverage. |
| Advertiser/page categories | `metadata.page_categories`, falling back to `snapshot.page_categories` | Multi-label page-category indicators; preserve the observed category strings. |
| Page entity type | `snapshot.page_entity_type`, falling back to a top-level field | Categorical ad-level comparison. |
| CTA | `snapshot.cta_type` | Categorical ad-level comparison; missing is explicit. |
| Active dates | `metadata.start_date`, `metadata.end_date` | Preserve raw values and report actual coverage. Do not impute an end date for still-active ads. |
| Lifetime | `metadata.total_active_time`; plus an optional derived `end_date − start_date` interval | Preserve `total_active_time` raw because its unit is not established. Derive days only when both dates parse and end ≥ start; retain the raw dates and document the conversion. |
| Image classifications | 320k user-classified image assets, joined by media hash through `ad_media.hash → ad_archive_id` | Report labeled-asset coverage and ad-level coverage separately. De-duplicate labels per image, then aggregate image labels to ad presence. Unlabeled images/ads are missing, never negative. |

The image input can be CSV/TSV, JSON/JSONL, or the legacy `extract_media.py` results SQLite database. The default image ID field is `media_hash`/`hash`; `--label-id-column` supports a differently named column **only when its values are the `ad_media.hash` keys**. A file already keyed by ad ID may use `ad_archive_id`/`ad_id`. Confirm the user’s actual schema and join key before treating the 320k figure as 320k unique, labeled, or linkable assets.

The RQ3 output is descriptive: ad-level prevalence differences, risk differences with Wald intervals, odds ratios with a small-cell correction for effect-size stability, Pearson tests, and Benjamini–Hochberg-adjusted p-values. These are exploratory associations, not causal effects; clustered or adjusted models and human validation are needed for publication-level claims.

## Repository map

- `analysis/pipeline.py` — consolidated, local-only RQ1/RQ2/RQ3 analysis.
- `analysis/README.md` — input contracts, definitions, run instructions, and output inventory.
- `analysis/tests/` — standard-library smoke/integration tests with synthetic data.
- `analysis/legacy/` — original analysis scripts, preserved as provenance.
- `collection/legacy/` — recovered collector, schema, snapshot workflow, and visualization notebook.
- `data/redirection_results/` — original geolocated final-URL observations.
- `archive/` — source bundles/exports preserved for provenance.
- `paper/drafts/` — current PDF draft.
- `paper/latex/AnonymousSubmission/LaTeX/` — reconstructed content sections, tables, bibliography, and original template files.
- `paper/INTRODUCTION_DRAFT.md` and `paper/SECTION_CONSOLIDATION.md` — proposed narrative and paper plan.
- `notes/archive/` — prior research/analysis notes, not automatically verified.

The LaTeX export is an AAAI 2026 template. It is retained as provenance only; **do not import template/camera-ready instructions into the paper’s argument or content.**

## Immediate next steps

1. Provide the full ad database and image-classification file/schema (or point `--db` and `--image-labels` at them), confirm whether image rows join by BLAKE2b media hash, filename, or ad ID, and record the exact collection snapshot/version.
2. Install/use `tldextract` for PSL-consistent domain parsing and rerun `analysis/pipeline.py` on the full database, image labels, and probes.
3. Reconcile all old table counts at the ad level, document denominators and overlaps, and decide whether any manually validated subset supports language stronger than “candidate signal.”
4. Fill the availability/coverage tables, then write the RQ1→RQ2→RQ3 results and figures from generated outputs—not the stale draft tables or hard-coded legacy plotting arrays.
5. Complete a targeted literature search and revise the novelty paragraph narrowly around the Meta-ad URL/creative linkage and actual evidence collected.
