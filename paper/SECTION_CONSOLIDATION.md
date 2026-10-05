# Paper consolidation and writing plan

This plan reorganizes the existing six-page draft around the requested order: **RQ1 URL characterization → RQ2 URL cloaking signals → RQ3 cloaked/non-cloaked ad differences**. It preserves useful material but removes duplicate RQ sections, unsupported claims, and stale totals from the active narrative.

## Proposed paper outline

### 1. Introduction

Use `INTRODUCTION_DRAFT.md`. Keep the motivating distinction among a displayed caption, the embedded link, and the observed destination. End with the three questions in their new order and three bounded contributions. Do not claim first-ever ad cloaking work, a unified definition of cloaking, or proof of malicious intent from the current proxies.

### 2. Background and related work

Replace the current long taxonomy and “research gap” section with a short synthesis of four strands:

1. **Web/search cloaking and conditional delivery:** establish that cloaking predates this work; discuss crawler-versus-browser comparisons and the Google Ads study by Invernizzi et al. (2016).
2. **URL shortening, redirection, and online-ad abuse:** distinguish ad-based shorteners, abusive traffic distribution, malicious redirection, and split-view cloaking. Avoid treating these as synonymous phenomena.
3. **Meta/Facebook Ad Library auditing and advertising research:** cover ecosystem measurement, independent political-ad auditing, archive/security limitations, problematic-ad delivery, and related ICWSM work. Explicitly state how those populations/questions differ from this study’s embedded-URL analysis.
4. **Brazilian ad-transparency context:** use Santini et al. (FAccT 2024) to situate the data source and its limitations in Brazil.

Keep this section proportional to the paper. A related-work table can summarize *platform/data*, *unit*, *behavior studied*, and *relationship to this study*. Do not call a work “closest” unless that comparison has been checked against its full text. Replace the draft’s sentence that there are “no previous studies” with the narrow, carefully qualified positioning in the overview.

### 3. Data, collection, and ethics

Consolidate the current `Data Collection` material from `sections/methods.tex` into a reproducible account:

- Collection dates, country/market, search strategy, capture software/version, query parameters, archive/API/UI source, restart logic, deduplication key, and what one row represents.
- Verify the claimed `407,771` records, “full media + metadata” coverage, and `600+ GB` against the stored database and collection logs. State missing/failed records and whether counts refer to ads, snapshots, or ad-media pairs.
- Document the library’s known limitations and why the collection strategy cannot establish the total number of ads in circulation. The draft’s claim that a special-character search is equivalent to an unfiltered search needs the actual protocol, replication evidence, and limitations; do not present it as proven completeness from a few search checks.
- Describe media extraction separately from ad-metadata capture. Report unique image assets, video assets, failed media, duplicate assets, and label coverage as different counts.
- Explain the redirect probes: exact requested URLs, country/IP locations, request repetition, probe dates, user agents, browser/cookie state if known, response/final-URL collection method, and per-request error handling. If the raw files record final URLs only, say so; do not imply complete hop traces.
- Include privacy/ethics handling for public ad content and potentially sensitive URL query parameters. The consolidated pipeline omits raw URLs/captions by default.

Move the old ad-format table here only after regenerating it. Keep a separate collection-flow/coverage table if the audience needs it; do not overload the method text with unsupported comparisons to unrelated ad datasets.

### 4. Measurement design

Use one concise operationalization section before the RQ results. Define, with examples and denominators:

- **URL units:** ad, link/card occurrence, normalized exact URL, registered domain, public suffix, advertiser/page.
- **Caption/link mismatch candidate:** how URL-like caption domains are extracted and compared; what happens when caption text is not a URL.
- **Card-domain heterogeneity candidate:** whether any distinct card destinations are counted or a specific “hidden card” pattern is manually coded. These are not equivalent.
- **Probe outcomes:** source/final registered-domain comparison, exact-URL matching, number of distinct final domains, country-level outcome differences, repeated outcomes, failures, and the legacy source-domain fallback.
- **Primary RQ2 union:** deduplicated ad-level union. One external final destination is descriptive and should not count as cloaking by itself.
- **RQ3 grouping and image join:** the candidate-signal group, comparison group, image-hash linkage, asset-to-ad aggregation, and missing-label treatment.
- **RQ3 fields:** availability and coding for `publisher_platform`, `page_categories`, `page_entity_type`, `cta_type`, `start_date`, `end_date`, `total_active_time`, and derived lifetime. Report actual coverage before showing group comparisons.

Distinguish Meta’s policy definition from the study’s operational measures. A caption mismatch, heterogeneous card domains, or geolocation-dependent endpoint is a measurement outcome; it does not by itself establish a policy violation or intent to deceive.

### 5. Results

Organize results in the same order as the RQs, with denominators and confidence intervals where meaningful.

#### 5.1 RQ1: URL characterization

- How many ads have a parseable web link? How many link occurrences, normalized URLs, registered domains, and advertisers are observed?
- Describe link counts and URL structure, domain concentration, public-suffix mix, advertiser reuse, and Meta-owned destinations using explicit units.
- Compare suffix mix for domains used by one, 2–10, 11–100, 101–1,000, and >1,000 distinct advertisers. Explain whether bars count unique domains, advertiser-weighted domains, or link occurrences.
- Compare display formats and destinations. Use a PSL-backed domain parser and identify its bundled version.
- Tranco rank is an external popularity proxy only; record the list date/version and matching method. Do not call rank a safety or trust score.

#### 5.2 RQ2: URL cloaking signals

- Report caption/link mismatch, card-domain heterogeneity, and exact-URL destination variation as separate ad-level signals, then give their deduplicated union.
- Show the legacy registered-domain aggregation only as a sensitivity analysis; it can merge distinct paths/URLs and over-attribute a probed outcome.
- Separate ordinary single external destinations from multiple/conditional final-domain variation. Do not label a simple source-to-destination redirect as cloaking.
- For geo outcomes, show country coverage, repeated observations, errors, unresolved URLs, within-country variation, and between-country differences. Use a country-by-outcome matrix or an observed final-domain flow visualization—not a “redirect chain” Sankey unless full hop data exist.
- Manually audit a stratified sample of each candidate type, including benign controls. Report inter-rater agreement and false-positive examples if the paper makes stronger intent-related claims.

#### 5.3 RQ3: image and metadata comparisons

- Start with an input-coverage table: labeled assets, matched assets, unmatched assets, ads with at least one label, ads with multiple labeled images, and the number of distinct labels.
- Aggregate images to ad-level label presence (and optionally label count), keeping image-level and ad-level results distinct. Do not turn absent labels into negatives.
- Compare categories of `publisher_platform`, `page_categories`, `page_entity_type`, and `cta_type`; separately compare field missingness.
- Compare active-date availability. Report raw-date coverage and a carefully defined derived lifetime only if the dates have interpretable encodings. Do not assume the unit of `total_active_time`.
- Use effect sizes and confidence intervals. If ads share advertisers, pages, assets, or campaigns, account for dependence in inferential models or label the unadjusted comparisons exploratory. Correct for multiple comparisons and report cell sizes.

### 6. Discussion

Interpret only patterns supported by the measurements. Address legitimate explanations for mismatches and destination diversity; distinguish link obfuscation from actual conditional content delivery; discuss what a platform transparency snapshot cannot reveal; and describe how controlled reviewer/user experiments or manual landing-page checks could strengthen future work. Low-resource moderation suggestions belong here only if tied to demonstrated signals and evaluated trade-offs.

### 7. Limitations and ethics

Make the following explicit:

- The Ad Library sample is not necessarily the complete set of ads shown or active during collection.
- The current repository lacks the full ad database and the 320k image-label file, so RQ1/RQ3 coverage has not yet been reproduced here.
- Probe results contain request errors and final URLs, not necessarily every redirect hop; geolocation is not reviewer/user identity.
- `tldextract` is not installed in the current environment. Probe-only diagnostics used a limited suffix fallback; rerun all domain results with PSL support before publication.
- Observable signals are not proof of deception; localized, tracked, affiliate, and multi-product links are plausible alternatives.
- Current image and metadata comparisons are observational, potentially clustered, and depend on label quality and join coverage.
- Public URLs may contain tracking or personal information; minimize exports and redact examples.

### 8. Conclusion

Answer each RQ in one sentence based on the final rerun, state the paper’s narrow contribution, and avoid generalized prevalence claims beyond the sample and measurement definitions.

## Existing manuscript material: keep, merge, revise, or set aside

| Current source | Action |
|---|---|
| `sections/intro.tex` | Replace with the RQ1→RQ2→RQ3 framing in `INTRODUCTION_DRAFT.md`. Remove “first of its kind,” the proposed 20-year unified definition, and policy-effect claims. |
| `sections/related.tex` | Rebuild around the four strands above. Retain checked citations; correct bibliography metadata and avoid an unsubstantiated “no prior work” gap claim. |
| `sections/methods.tex` — collection | Keep the collection provenance, but add reproducibility details and revalidate all counts, search-completeness claims, and format percentages. Move probe details into measurement design. |
| `sections/methods.tex` — “Cloaking Detection” | Convert to operational definitions and limitations, not findings. Avoid repeating definitions in Results. |
| `sections/results.tex` | Reorder results by new RQ1, RQ2, RQ3. It currently begins with a domain subsection, then “Internal Cloaking,” while the RQ headings are elsewhere and some are empty. Consolidate to one active Results section. |
| `sections/result_bp.tex` | Preserve as legacy scratch/provenance. It contains commented-out material and conflicting older counts; do not compile or copy its table totals without a fresh ad-level rerun. |
| `tables/totals.tex` | Regenerate from `format_pattern_summary.csv`; expose denominators and overlaps. Correct the percentages flagged in `PROJECT_OVERVIEW.md`. |
| `tables/taxonomy.tex` | Retain only if the final operational taxonomy is useful and evidence-based. Do not use a broad taxonomy merely to claim a unified definition. |
| `figs/` referenced by the `.tex` files | The referenced source images are absent from the reconstructed tree. Recreate figures from pipeline outputs or recover their sources; do not assume the PDF’s rasterized versions are reproducible. |
| `aaai2026.sty`, `.bst`, template `.tex` | Provenance only. **Do not incorporate CameraReady/AAAI formatting instructions into the paper.** |

## Figure and table plan

Prioritize a small, coherent set of figures that the available data can support:

1. **Collection and join flow** (counts by stage): collected ad rows → parseable links → probe-matched URLs → labeled assets → ads with image labels. Add after actual inputs are available.
2. **RQ1 URL concentration:** top destination domains plus an empirical CDF of per-domain link occurrences, with advertiser strata clearly labeled. A top-domain plot is descriptive; do not expose sensitive query strings.
3. **RQ1 suffix composition:** unique-domain share beside advertiser-weighted share by advertiser stratum. Use a small “other suffixes” category and identify the PSL version.
4. **RQ2 signal prevalence by ad format:** rates and denominators for each signal and the deduplicated union. Show the legacy domain-level scope separately or in a sensitivity panel.
5. **RQ2 destination variation:** country-by-outcome heatmap or final-domain source→destination graph with edges aggregated by exact requested URL. Label final-domain transitions as observed outcomes, not hops.
6. **RQ3 image-label effects:** risk-difference forest plot with 95% intervals for sufficiently common labels, alongside cell counts and the label-coverage table. A separate concise table/plot can show metadata availability and key platform/CTA/category differences.
7. **Qualitative examples:** a small, manually validated and redacted ad example for each signal. Remove account/page names, query tokens, phone numbers, and tracking IDs; include benign counterexamples.

Use the pipeline’s generated plots as exploratory starting points, not final figures. The current code can produce RQ1 domain/CDF/suffix plots, an RQ2 format-prevalence plot, a final-domain-flow plot, and an RQ3 image-label risk-difference plot when the corresponding inputs exist and optional `matplotlib` is installed.

## Feasibility matrix in the current checkout

| Analysis | Current status | What is needed before paper claims |
|---|---|---|
| Probe-file coverage and final-domain outcomes | Runnable now on four checked-in JSON files; 26,278 URL keys match across countries. Initial counts are in `PROJECT_OVERVIEW.md`. | Rerun with `tldextract`; document probe timing, repetition, request state, errors, and whether output lists are final URLs only. These counts are not full-ad prevalence. |
| Full RQ1 URL/domain characterization | Not reproducible from this checkout; no ad database. | Full SQLite ad DB, verified sample/dedup units, and PSL parser. |
| Caption/link mismatch and card destination heterogeneity | Pipeline implemented, but no full ad metadata database is present. | Full DB; manually coded validation sample; clear rules for URL-like caption text and card formats. |
| RQ2 destination variation | Probe-only source data exists; exact URL → ad join not yet possible without full DB. | Full DB and exact URL matching audit; keep exact-URL and legacy domain aggregation separate. |
| 320k image-label comparison | Not reproducible; label file/schema and join key are absent. | Classification file/table, label taxonomy, image IDs, confidence/duplicate policy, and validation of `ad_media.hash → ad_archive_id`. |
| Publisher platform, category, entity type, CTA, dates/lifetime | Older notebook attempts these fields, but current-database coverage is unknown. | Full DB; use `metadata_field_availability.csv`, then report coverage and missingness before comparisons. |
| Manual intent/policy-violation claims | Not established by current evidence. | Human review, evidence of conditional content delivery, policy mapping, and counterexamples; otherwise use “candidate signal.” |

## Venue and length strategy

For an ICWSM-facing narrative, foreground how an ad’s link, creative, page/category, and platform context relate, and be precise about the Ad Library’s selection/coverage. For WWW or a security venue, emphasize URL-level measurement, exact matching, error treatment, destination variation, validation, and reproducibility. Venue choice must follow the completed results and contribution—not the presence of a recovered AAAI template.
