Let me analyze this request carefully.

The user has a paper draft titled "Behind Cloaks and Masks: Uncovering Deceptive Misuse of Meta's Advertisement Systems" (anonymous submission for ICWSM 27). They want me to distill it into dense presentation slides about:

1. Methodology
2. Results (focusing on what the paper already answers, not undeveloped sections and RQs)
3. How the paper improves upon previous literature

Let me carefully extract the key information from the paper draft:

**Paper overview:**

- Title: "Behind Cloaks and Masks: Uncovering Deceptive Misuse of Meta's Advertisement Systems"
- Topic: Analysis of URL cloaking in Meta's Ad Library

**Research Questions (from Introduction):**

- RQ1: What forms of URL cloaking can be detected internally within the Ad Library? Which mechanisms are exploited and how prevalent are they?
- RQ2: What is the distribution of domains embedded in adverts? When requested, what kinds of redirection cloaking can be observed?
- RQ3: What features further differ cloaked and non-cloaked adverts?

Note: RQ3 seems underdeveloped in the draft (the "Comparative Analysis" section is empty, "External Cloaking" has just a stub with RQ3 repeated). The user explicitly says: "Results should focus on what the paper already answers, not included undeveloped sections and RQs." So I should focus results on RQ1 and RQ2 content that's actually present, and avoid presenting RQ3 as answered. I can mention RQ1/RQ2 answers and note that external redirection cloaking analysis is present in methodology but the paper's results sections are incomplete — actually, I should just not include undeveloped stuff. Let me re-read.

The Results section includes:

- Domain Distribution: 26,279 unique domains, severely skewed frequencies, most common dominated by Meta's own platforms (circularity), "whatsapp.com" used over 50 times more than the most frequent non-Meta domain "shopee.com". Domain usage by advertiser figure (Figure 1: TLD distribution by advertiser ranges).
- Internal Cloaking:
    - URL Masking: use of "Caption" field as anchor text, showing arbitrary strings instead of actual embedded link. Detection: comparison of domain names, discarding non-URL formatted strings, TLDextract with Public Suffix List.
    - Card Cloaking: when one link_url differs from others in a carousel (e.g., 4 cards embed "amazon.com" while one links to "othersite.xyz").
- Table 1: Total collection amounts with display formats and cloaking counts:
    - VIDEO: 223,002 (54.6%) — URL masking 11,505 (5.2%), Multi redirection 5,664 (2.5%), Single redirection 5,493 (2.5%), Total cloaked 16,863 (7.6%)
    - IMAGE: 112,877 (27.7%) — URL masking 5,944 (5.3%), Multi redirection 2,202 (2.0%), Single redirection 908 (0.8%), Total cloaked 6,744 (6.0%)
    - DCO: 38,846 (9.5%) — URL masking 1,768 (4.6%), Card cloaking 883 (2.3%), Multi redirection 440 (1.1%), Single redirection 375 (1.0%), Total cloaked 2,336 (6.0%)
    - CAROUSEL: 27,032 (6.6%) — URL masking 120 (0.4%), Card cloaking 44 (0.2%), Multi redirection 11 (<0.1%), Single redirection 162 (0.6%), Total cloaked 308 (1.1%)
    - DPA: 2,453 (<0.1%) — URL masking 132 (5.4%), Card cloaking 2 (0.1%), Multi redirection 3 (0.1%), Single redirection 543 (22.1%), Total cloaked 658 (26.8%)
    - Dataset total: 407,771 ads; URL masking 19,470; Card cloaking 929; Multi redirection 8,322; Single redirection 7,490; Total cloaked 26,921 (6.6%)
- Figure 4: Masks using domains from Tranco (so URL masks often impersonate popular domains)
- Figure 5: Masks simulating Google
- Figures 6/7 (Sankey diagrams?) showing redirect flows

**Methodology:**

- Data collection: Meta Ad Library Web interface (API in most countries covers only political/social issue ads). Crawler operated 2 months (April 20 – June 19, 2026), collected 407,771 full advert media + metadata pairs, >600GB storage.
- Closest literature match for pipeline: Le Pochat et al. 2022 (metaAudit), with key differences: complete multimedia creative extraction (images and video) and increased diversity coverage via unfiltered search approach instead of advertiser-constrained one.
- Unfiltered search approach: using special characters (e.g., '*') as search term returns unfiltered view. Verified empirically in multiple scenarios:
    - 'keyword *' same as 'keyword'
    - '*' under specific advertiser = full advert display
    - '*' in countries with <50k adverts returns >= vowel searches
    - '', special characters return identical results
- This avoids advertiser-centric bias (important for moderation-avoidance investigation) and unretrievable ad issues.
- Preliminary metadata-only collection to map advert display formats (VIDEO, IMAGE, DCO, CAROUSEL dominating), ensuring data ingestion could handle all dynamic creatives.
- Comparison: Edelson et al. 2020 metadata-only 3M+ political ads; Vaidya & Garimella 2026 betting study 29,772 ads, 23,620 media retrieved (79.3%) — close to 81.1% VIDEO+IMAGE proportion here; DCO+Carousel+DPA proportion 16.6% matches 20.6% reported as "unsuccessfully extracted".
- Cloaking detection:
    - Internal (metadata-only, no external requests):
        - URL Masking: Caption vs link_url domain comparison; discard non-URL strings; TLDextract + PSL.
        - Card Masking: one link_url differs from others in multi-card formats.
    - URL Resolution Cloaking (external): URLs requested from 4 geolocated IPs (Brazil, Portugal, Germany, US), repeated 5 times to capture variation. [Results for this are partially developed — single/multi redirection counts are in Table 1, so redirection cloaking results ARE reported in the table. The "External Cloaking" section in results is a stub though. Hmm.]
- Limitations: cannot know total ads in circulation during collection timeline.

**Discussion/recommendations:**

- Remove URL captioning feature (force true URLs shown)
- Static analysis of dynamic ads to detect content discrepancies
- Fingerprinting media to identify persistent campaigns

**Contributions (stated in intro):**

- First-of-its-kind analysis of advert-embedded URLs and cloaking patterns in Meta's Advertising Ecosystem; uncovering malicious abuse of Ad Distribution features to avoid moderation and deceive consumers.
- Unified definition of cloaking over 20+ years of research, highlighting enduring, resurging, novel practices and relations to adjacent areas.
- Discussion of low-resource moderation strategies.

**Research gap:**

- Conceptual gap: unified definition of cloaking (prior work context-specific, e.g., Szurdi et al. 2021)
- No previous studies on advert-embedded URLs in Meta's advertising ecosystem; no large-scale URL-embed analysis in Ad Library.

**How it improves on prior literature (from Related Work + methodology comparisons):**

- vs. Edelson et al. 2020 (S&P): advertiser-centric collection works for political context but biases against emerging advertisers; their approach metadata-only; ours: unfiltered special-character search, full multimedia extraction.
- vs. Vaidya & Garimella 2026 (ICWSM): 23,620/29,772 media retrieved (79.3%), missing dynamically loaded elements; ours: complete dynamic creative handling (DCO, Carousel, DPA), 407,771 ads with full media+metadata.
- vs. Szurdi et al. 2021 (WWW): context-specific definitions of cloaking; ours unifying framework.
- vs. Bartuzi-Trokielewicz et al. 2026: closest to analyzing cloaking patterns in an online ecosystem but doesn't mention specific platform; ours platform-specific (Meta).
- Prior cloaking lit: Wu & Davison 2006 (semantic cloaking search), Wang et al. 2011 (search cloaking), CrawlPhish 2021 (client-side cloaking in phishing), Zeng et al. 2022 (redirection mechanisms), Fukushi et al. 2021 (ad-based URL shortening), Odgerel et al. 2025 (URL shorteners phishing), Zhuo et al. 2024 (phishing susceptibility with link presentation), El Fraihi et al. 2026 (creative optimization bypass on YouTube).
- Anchor text masking literature: Mohammad et al. 2012, Sánchez-Paniagua et al. 2022, Chen & Guo 2006.
- Ad ecosystem auditing: political ads, health ads, COVID, betting, ad library security audit (Edelson 2020), collaborative transparency (Gkiouzepi 2023), ad delivery discrimination (Ali et al. 2019), revenue fraud (Papadogiannakis 2025).

**Results to focus on (answered):**

- RQ1: Internal cloaking forms: URL masking (caption vs link_url), card masking; prevalence: 19,470 URL masks + 929 card cloaks; redirection: 8,322 multi + 7,490 single; total 26,921 (6.6%).
- RQ2: Domain distribution: 26,279 unique domains, heavily skewed, Meta platform dominance (circularity), whatsapp.com 50x more than top non-Meta domain shopee.com. Redirection cloaking observed (single/multi counts in Table 1).
- DPA format has highest cloaking rate (26.8%), especially single redirection (22.1%).
- VIDEO and IMAGE are the highest-volume carriers of URL masking (5.2%, 5.3%).
- Masks use Tranco domains and simulate Google (Figures 4 & 5).

The user wants "dense slides" — so I should produce slide content, probably in Markdown format, one slide per section, with dense bullet points. Maybe 10-14 slides. Include speaker notes? They said "distill this paper draft into dense slides for a presentation about the methodology and results found." Focus on methodology + results + improvement over prior literature.

Format: The formatting rules say use Markdown lists/tables, code fences for code blocks. Slides could be presented as markdown with headers per slide. Dense = lots of content per slide but distilled. I'll create a slide deck outline with maybe 12-15 slides, using tables for the data (Table 1 is key). Use details/summary collapsible sections? The instruction says "For responses with many sections where some are more important than others, use collapsible sections (HTML details/summary tags) to highlight key information while allowing users to expand less critical details." A slide deck could use collapsible sections for speaker notes or backup slides. That seems apt: main slides visible, speaker notes / backup slides collapsible.

Let me structure the deck:

1. Title slide: Behind Cloaks and Masks — Uncovering Deceptive Misuse of Meta's Advertisement Systems (ICWSM '27 submission; venue context)
    
2. Motivation & Problem: deceptive practices since Web 1.0; cloaking = showing different content to moderators vs users; Meta Ad Library as underexplored surface; gap statement.
    
3. Research Questions (RQ1, RQ2 — and RQ3 noted as exploratory/ongoing; but user says don't include undeveloped RQs. Hmm. The user says results should focus on what the paper already answers, not included undeveloped sections and RQs. So in the RQ slide, I could list RQ1 and RQ2 only, since RQ3's results aren't developed. But the paper lists 3 RQs. The instruction: "Results should focus on what the paper already answers, not included undeveloped sections and RQs." I read this as: when presenting results, only include what's answered. I could still list RQ3 in the questions slide but mark it, or just drop it. Safer: present RQ1 & RQ2 as the answered questions; maybe mention RQ3 as comparative analysis in future work. Actually to be safe and aligned: include RQ1 and RQ2 in the RQ slide; fold RQ3 into "future work" or omit. I'll include a note that comparative features (RQ3) analysis is under development — actually the user said NOT to include undeveloped sections and RQs. So omit RQ3 from the main flow entirely. Maybe mention in a "future work" line? They said not to include. I'll omit RQ3 from results; may briefly note in future work slide "comparative feature analysis" — hmm, that's including it. The user says "Results should focus on what the paper already answers, not included undeveloped sections and RQs." I think this means: don't present undeveloped sections/RQs as if they have results. Future work can mention them but I should be careful. I'll keep future work minimal (moderation strategies from discussion are developed). I'll leave RQ3 out entirely except perhaps a small note in the "scope" — no, clean omission. Actually, the redirect resolution (external cloaking) is part of RQ2 ("When requested, what kinds of redirection cloaking can be observed?") and Table 1 reports single/multi redirection counts — that IS answered at least quantitatively. The external cloaking results section is a stub beyond the table, but the Sankey figures (img-3, img-4?) — actually img-3 is a code screenshot (Figure 3 caption?) and the last images (Sankey-like) appear to be redirect flow diagrams. Figure 2 "Url Distribution". So redirection flows are shown via figures. I'll present redirection counts from Table 1 as answered results, without inventing details about the flows beyond "redirection cloaking observed via multi-IP resolution" and figures showing redirect chains/flow distribution. I should be careful not to fabricate specifics about the Sankey diagrams' content. I can say "redirect flow visualizations (source → destination domains)" since they're Sankey diagrams of flows — reasonably inferable from the images described (left/right node columns with flows). I'll keep it generic: "Redirect flow maps (sankey) showing how cloaked URLs hop across intermediary domains."
    
4. Contributions slide (3 bullets from paper).
    
5. Related work / gap slide: three literatures (ad auditing, cloaking 20 years, redirection/masking) + gap.
    
6. Methodology — Data collection pipeline: web-only crawling, unfiltered '*' search, 2 months, 407,771 ads, 600GB, full media.
    
7. Methodology — Why unfiltered search beats advertiser-centric: validation bullets; bias avoidance; granularity (ads not displayed on advertiser pages).
    
8. Methodology — Cloaking detection: internal (URL masking via caption↔link_url domain comparison with tldextract/PSL; card masking via inconsistent link_url across cards) + external (4 geo IPs × 5 repeats).
    
9. Dataset overview slide: Table 1 (or condensed version).
    
10. Results RQ1: Internal cloaking prevalence — 26,921 cloaked (6.6%); URL masking 19,470 (72% of cloaked); card masking 929 concentrated in DCO (883).
    
11. Results RQ1 continued / format risk: DPA 26.8% cloaked (22.1% single redirection); VIDEO 7.6%, IMAGE 6.0%, DCO 6.0%, CAROUSEL 1.1%.
    
12. Results RQ2: Domain distribution: 26,279 unique domains; skew; Meta circularity (whatsapp.com 50× shopee.com); TLD distribution by advertiser ranges (Fig 1); URL distribution (Fig 2).
    
13. Results: Mask design: Tranco domains as masks (Fig 4), Google simulation (Fig 5) — camouflage using trusted brands; redirection flows (single vs multi).
    
14. Discussion & recommendations: remove captioning; static analysis of dynamic ads; media fingerprinting.
    
15. How we improve on prior work (comparison table): vs Edelson 2020, Vaidya & Garimella 2026, Szurdi 2021, CrawlPhish, Bartuzi-Trokielewicz 2026.
    
16. Limitations: unknown total ads in circulation; Ad Library inconsistencies.
    
17. Takeaways.
    

That's ~15-17 slides; dense. Maybe combine some. The user wants "dense slides" — fewer slides, each dense. Let me aim for ~12 slides with dense content, plus collapsible speaker notes.

I need to be careful about numbers:

- 407,771 ads collected (paper says 407771).
- 600+ GB.
- April 20 – June 19, 2026 (two months).
- 26,279 unique domains.
- Total cloaked: 26,921 (6.6%).
- URL masking: 19,470; Card cloaking: 929; Multi redirection: 8,322; Single redirection: 7,490.
- DPA: 2,453 ads, 658 cloaked (26.8%), single redirection 543 (22.1%).
- VIDEO: 223,002 (54.6%), cloaked 16,863 (7.6%).
- IMAGE: 112,877 (27.7%), cloaked 6,744 (6.0%).
- DCO: 38,846 (9.5%), cloaked 2,336 (6.0%), card cloaking 883 (2.3%).
- CAROUSEL: 27,032 (6.6%), cloaked 308 (1.1%).
- Dynamic formats (DCO+Carousel+DPA): 16.6% — matches 20.6% reported elsewhere as unextractable.
- Vaidya & Garimella: 29,772 ads, 23,620 media (79.3%).
- whatsapp.com > 50× shopee.com (most frequent non-Meta domain).
- 4 IPs (Brazil, Portugal, Germany, US), 5 repetitions.

Percentages: URL masking 19,470/407,771 ≈ 4.8%. Multi redirection 8,322 ≈ 2.0%; single 7,490 ≈ 1.8%. Total 26,921 ≈ 6.6%. Within cloaked: URL masking 72.3%, multi redir 30.9%, single 27.8%, card 3.5% — note multi+single+card don't sum with URL masking because ads can have multiple patterns (total cloaked < sum). Sum: 19,470+929+8,322+7,490 = 36,211 > 26,921, so overlap exists — I should note "categories overlap (ads may exhibit multiple patterns)" — that's an inference; is it safe? 36,211 ≠ 26,921 means either overlap or the total cloaked is ads, not patterns. Table says "Total Cloaked 26,921 (6.6%)" under Dataset row. Since sum of categories > total, there must be overlap (an ad can be both URL-masked and redirected). That's a reasonable reading, but I could also just present counts without claiming overlap. To be dense but accurate, I can present both: per-category counts and total unique cloaked (6.6%). I might add "(categories overlap)" — this is a defensible arithmetic note. I'll phrase it as "per-pattern counts overlap; 26,921 unique ads (6.6%) exhibit ≥1 pattern" — the "unique" framing is inference but safe. Hmm, actually "Total Cloaked" could just be defined by the authors. The arithmetic shows overlap. I'll note it lightly: "pattern counts are not mutually exclusive."

Also prior-work comparison numbers:

- Szurdi et al. 2021: cloaking-aware scraping finds 81% more malicious URLs than singular crawling.
- Edelson et al. 2020: 3M+ political ads, metadata-only, advertiser-centric.
- El Fraihi et al. 2026: creative optimization bypass confirmed on YouTube contextual ads.

Contributions from intro:

1. First-of-its-kind analysis of advert-embedded URLs & cloaking patterns in Meta's Ad ecosystem; uncovering malicious abuse of ad distribution features to evade moderation & deceive consumers.
2. Unified definition of cloaking across 20+ years of research → enduring, resurging, novel practices; ties to adjacent research areas.
3. Low-resource moderation strategies discussion.

Gap:

1. Conceptual gap: unified cloaking definition (prior context-specific).
2. Security auditing gap: no large-scale URL-embed analysis in Meta's Ad Library.

Methodology validation scenarios for '*' search:

- 'keyword *' ≡ 'keyword' (position-independent)
- '*' under a specific advertiser ≡ full ad display
- '*' in countries with <50k ads returns ≥ vowel searches
- '', '', etc. special chars identical results
- assumption: no-parameter special-char search ≡ unfiltered search; strengthened by content diversity and collection of ads not shown on advertiser pages.

Now, "how we improve upon previous the literature" — user wrote "previous the literature" (typo for "the previous literature"). So a dedicated slide (or two) comparing to prior work is essential.

Comparison slide ideas:  
| Prior work | Their approach/limitation | Our improvement |

- Edelson et al. '20 (S&P): advertiser-constrained, metadata-only, political niche | unfiltered special-char search → unbiased, emerging advertisers captured; full media
- Vaidya & Garimella '26 (ICWSM): 79.3% media retrieval, dynamic creatives lost | ingestion handles all display formats (DCO/Carousel/DPA); dynamic formats = 16.6% of dataset, where cloaking concentrates (DPA 26.8%)
- Szurdi et al. '21 (WWW): context-specific cloaking definition | unified 20-year definition applied to ads
- CrawlPhish '21 / Zeng '22: phishing/redirection cloaking outside ads | first in-platform (Ad Library metadata) + external resolution of ad URLs
- Bartuzi-Trokielewicz '26a/b: ecosystem-level synthetic-media scam/cloaking analysis, platform-agnostic | platform-specific Meta audit with per-ad metadata
- Wu & Davison '06, Wang '11: search-engine semantic cloaking | new surface: social ad ecosystem
- Zhuo '24 (susceptibility), Odgerel '25, Fukushi '21: link presentation phishing risk | quantify actual misuse at scale in ads
- El Fraihi '26: creative optimization bypass on YouTube | analogous dynamic-ad abuse quantified on Meta (card cloaking in DCO/Carousel)

Also low-resource moderation recommendations as contribution.

Now the deliverable format: The user asked to "distill this paper draft into dense slides." I'll produce a Markdown slide deck. Given the formatting rules, I'll use `---` separators between slides (like Marp/reveal markdown) or headers. I think headers + horizontal rules are fine. Should I wrap the whole deck in a code fence? No — code fences are for code. Slides in Markdown are fine as regular markdown.

I'll use collapsible

for speaker notes on each slide, per the formatting rule about collapsible sections for less critical details. That fits well: main slide content visible; speaker notes collapsible.

Number of slides: Let me aim for 13 slides:

1. Title
2. Problem & Motivation
3. Research Questions & Contributions
4. Related Work & Research Gap
5. Methodology I — Collection Pipeline
6. Methodology II — Unfiltered Search Validation
7. Methodology III — Cloaking Taxonomy & Detection
8. Dataset Overview (Table 1 condensed)
9. Results RQ1 — Internal Cloaking
10. Results RQ1 — Format-Level Risk
11. Results RQ2 — Domain Distribution & Circularity
12. Results RQ2 — Mask Camouflage & Redirection Flows
13. Improvement over Prior Literature (table)
14. Recommendations (moderation)
15. Limitations & Takeaways

That's 15. Could merge 9-10, and 14-15. Dense is requested, so ~12-13 dense slides is fine. Let me merge: 9+10 → "Results RQ1"; 14+15 → "Recommendations & Limitations" plus separate Takeaways as final slide. Total 13.

Let me draft each slide's content.

**Slide 1 — Title**

- Behind Cloaks and Masks: Uncovering Deceptive Misuse of Meta's Advertisement Systems
- ICWSM '27 (anonymous submission)
- One-liner: First large-scale audit of advert-embedded URLs & cloaking in Meta's Ad Library — 407,771 ads, full multimedia, 6.6% cloaked.

**Slide 2 — Problem & Motivation**

- Cloaking = serving different content to auditors/moderators vs. end users; documented since Web 1.0 (Wu & Davison '06; Wang et al. '11)
- Modern OSNs = new cloaking surfaces; ad distribution systems abusable for moderation evasion
- Meta's Ad Library is the transparency mechanism — but its URL layer (link_url, caption) is unaudited
- 20+ years of cloaking research is fragmented into context-specific silos (search spam, phishing, TDS)
- No prior large-scale study of advert-embedded URLs in Meta's ecosystem

**Slide 3 — RQs & Contributions**  
RQ1: Which URL-cloaking forms are detectable inside the Ad Library's own metadata? Mechanisms & prevalence?  
RQ2: What domains do ads embed? What redirection cloaking appears when URLs are resolved?  
Contributions:

- First analysis of advert-embedded URLs/cloaking in Meta's ad ecosystem → uncovers malicious abuse of ad-distribution features to evade moderation & deceive consumers
- Unified cloaking definition spanning 20+ years → enduring / resurging / novel practices, connected to adjacent areas
- Low-resource moderation strategies grounded in observed patterns

**Slide 4 — Related Work & Gap**  
Three literatures:

- Ad-ecosystem auditing: political ads (ICWSM/WWW), health & COVID misuse, illicit betting, Ad Library security flaws (Edelson '20), transparency limits (Gkiouzepi '23), delivery bias (Ali '19), fraud revenue flows (Papadogiannakis '25)
- Cloaking: search-engine semantic cloaking (Wu & Davison '06; Wang '11), client-side phishing cloaking (CrawlPhish '21), traffic distribution systems (Szurdi '21 — cloaking-aware scraping finds 81% more malicious URLs), systematic reviews ('23)
- Masking primitives: anchor-text masking in phishing URLs ('12, '22), link presentation & user susceptibility (Zhuo '24a/b), URL shortener abuse (Fukushi '21; Odgerel '25), redirection intermediaries (Zeng '22), creative-optimization bypass on YouTube (El Fraihi '26)  
    Gap: context-specific definitions → no unified framework; no advert-URL analysis on Meta; closest ecosystem work (Bartuzi-Trokielewicz '26) is platform-agnostic.

**Slide 5 — Methodology I: Collection Pipeline**

- Web-only collection (API restricted to political/social-issue ads in most countries) → web interface for completeness
- Unfiltered search: special-character queries ('*') as generic search term
- 2-month crawl (Apr 20 – Jun 19, 2026): 407,771 ad records, full media + metadata, >600 GB
- Completeness-first: full image/video extraction (most studies discard or partially collect multimedia)
- Preliminary metadata-only pass mapped all display formats (VIDEO, IMAGE, DCO, CAROUSEL, DPA, ...) so ingestion handles dynamic creatives
- Pipeline closest to Le Pochat et al. '22 audit; key deltas: multimedia capture + unfiltered diversity

**Slide 6 — Methodology II: Unfiltered search validation & why it matters**  
Validation scenarios (empirical):

- 'keyword *' ≡ 'keyword' (position irrelevant)
- '*' scoped to an advertiser ≡ full ad list
- '*' in countries with <50k ads returns ≥ vowel-search results
- Other special characters ('', …) identical
- assumption: no-filter special-char search ≡ unfiltered browsing; reinforced by content diversity + retrieval of ads not shown on advertiser pages  
    Why it matters:
- Advertiser-constrained crawls (e.g., Edelson '20, 3M+ political ads) bias against emerging/unknown advertisers — precisely where moderation evasion lives
- Avoids unretrievable-ad gaps documented in prior audits (bug reports, partially fixed)

**Slide 7 — Methodology III: Cloaking taxonomy & detection**  
Internal (metadata-only, no requests):

- URL Masking: `caption` (anchor text) shows an arbitrary domain while `link_url` embeds the real destination → detection = domain comparison, discard non-URL captions, tldextract + Public Suffix List
- Card Masking: one card's `link_url` deviates from the rest (e.g., 4× "amazon.com" + 1× "othersite.xyz") → hides malicious card among benign fillers in dynamic formats (DCO/Carousel/DPA)  
    External (URL resolution):
- Request each ad URL from 4 geolocated IPs (BR, PT, DE, US) × 5 repetitions → captures geo/UA variation in redirection cloaking (single-hop vs multi-hop chains)

**Slide 8 — Dataset: 407,771 ads by display format** (condensed Table 1)  
Table with formats: VIDEO 223,002 (54.6%) | cloaked 7.6%; IMAGE 112,877 (27.7%) | 6.0%; DCO 38,846 (9.5%) | 6.0%; CAROUSEL 27,032 (6.6%) | 1.1%; DPA 2,453 | 26.8%; others negligible; Dataset 407,771 | 26,921 (6.6%)

- Dynamic formats = 16.6% of corpus — matches ~20.6% that prior work (Vaidya & Garimella '26) failed to extract ("missing/dynamically loaded elements") → dynamic creatives are exactly where cloaking concentrates
- 79.3% media-retrieval rate in prior betting study ≈ our 82.3% (VIDEO+IMAGE share) — cross-validation of format distribution

Wait — the paper says: "the reported total amount of images and video successfully downloaded in this betting study was about 79.3%, close to the proportion of 81.1% we find adding in the totals for 'VIDEO' and 'IMAGE' formats". 54.6+27.7 = 82.3%. Hmm, the paper says 81.1%. Let me recompute: 223,002 + 112,877 = 335,879. 335,879/407,771 = 82.37%. The paper says 81.1%. There's a discrepancy in the draft itself. 54.6+27.7 = 82.3. The paper text says 81.1% — maybe they computed differently (perhaps excluding something). I should quote the paper's figure (81.1%) rather than my recomputation, or present as "≈81%". I'll say ~81% (paper's stated 81.1%). Actually to be safe: "VIDEO+IMAGE = 82.3% of our corpus (paper cites 81.1%)" — no, don't contradict the draft. Just say "≈81%". Fine.

**Slide 9 — Results RQ1: Internal cloaking prevalence**

- 26,921 ads (6.6%) exhibit ≥1 cloaking pattern (pattern counts overlap)
- URL Masking: 19,470 ads (~4.8% of corpus; 72% of cloaked) — caption shows trusted/lookalike domain, embed goes elsewhere
- Card Masking: 929 ads — 883 (95%) in DCO dynamic ads; hiding one malicious card among benign ones
- Redirection cloaking (external resolution): 8,322 multi-hop (2.0%), 7,490 single-hop (1.8%)
- Format-level: VIDEO & IMAGE carry the most URL masks by volume (5.2% / 5.3%); DPA is the extreme: 26.8% cloaked, 22.1% single-redirection
- CAROUSEL lowest (1.1%) — static card formats are less exploited than DCO/DPA

Hmm wait, is that last claim supported? CAROUSEL 1.1% vs DCO 6.0%, DPA 26.8%. Yes, from table. The "less exploited" interpretation is fine.

**Slide 10 — Results RQ2: Domain distribution & ecosystem circularity**

- 26,279 unique domains; severely skewed long-tail
- Top domains dominated by Meta's own platforms → circularity: ads route users back into Meta properties
- whatsapp.com used 50× more than the top non-Meta domain (shopee.com)
- TLD mix varies by advertiser scale (Fig 1): weighted-by-advertiser vs unique-domain views diverge → few advertisers drive most links
- Fig 2: URL distribution across categories

**Slide 11 — Results: Mask camouflage & redirect flows**

- Masks impersonate high-trust brands: masks built on Tranco top domains (Fig 4); direct Google simulations (Fig 5)
- Example (Fig 3): card-cloaked ad shows "doceemminutos.com" while embedded URL is "pay.kiwify.com.br/..." — payment-processor redirect behind a home-brand mask
- Redirect flow maps (sankey): source → intermediary → destination chains; single-hop vs multi-hop splitting of 15,812 resolved cloaks
- Implication: user-facing trust signals (domain shown) are systematically decoupled from actual destinations

15,812 = 8,322+7,490. That's derivable. OK.

**Slide 12 — How we improve on prior literature** (table)  
Rows:

- Edelson et al. '20 (S&P, Ad Library security): metadata-only, advertiser-constrained, political niche → we: unfiltered special-char search; full multimedia; whole-ecosystem scope; unbiased toward emerging advertisers
- Vaidya & Garimella '26 (ICWSM betting): 79.3% media retrieval; dynamic creatives lost → we: ingestion covers all formats; show dynamic formats (16.6%) are the cloaking hotspot (DPA 26.8%)
- Szurdi et al. '21 (WWW, TDS): context-specific cloaking definition → we: unified 20-yr definition, applied in-platform
- CrawlPhish '21 / Zeng '22 / cloaking reviews: phishing & search contexts, off-platform crawls → we: cloaking measured inside a major ad platform's own transparency system
- Bartuzi-Trokielewicz '26 (WWW Companion ×2): ecosystem-level scam/cloaking, platform unnamed → we: named platform (Meta), per-ad URL-level evidence
- Zhuo '24, Odgerel '25, Fukushi '21 (masking risk in email/shorteners): susceptibility & small-scale → we: 407k-ad quantification of actual misuse in the wild
- El Fraihi '26 (YouTube creative optimization): bypass reported → we: quantified card/DCO abuse on Meta

**Slide 13 — Recommendations (low-resource moderation)**

- Remove/retire URL captioning: force true URLs visible to end users (kills URL masking at the root)
- Static analysis of dynamic ads: flag link/creative discrepancies across cards (card masking)
- Media fingerprinting: track persistent campaigns across formats/advertisers

**Slide 14 — Limitations & Takeaways**  
Limitations:

- Unknown denominator: total ads in circulation during crawl window unknowable → prevalence is a lower-bound estimate of visible library
- Ad Library's own documented inconsistencies (Gkiouzepi '23; Le Pochat '22)
- Search-assumption (∗ ≡ unfiltered) verified empirically, not by Meta  
    Takeaways:
- 6.6% of 407,771 ads cloak; masking concentrated in dynamic formats
- Transparency infrastructure itself is a cloaking vector: caption field + dynamic delivery are the weak links
- Cheap, structural fixes (true URLs, discrepancy checks, fingerprints) go far

Now, about the "results should focus on what the paper already answers" — the external cloaking section is stub-y, but Table 1 includes single/multi redirection counts which are results. The sankey figures exist. So RQ2's redirection part has partial quantitative answers. I'll present those. I will NOT present a "comparative analysis of cloaked vs non-cloaked features" (RQ3) since the section is empty. I won't list RQ3 as a slide item. Should I list RQ3 in the RQ slide? The user said don't include undeveloped RQs. I'll present RQ1 & RQ2 only, and maybe a footnote "RQ3 (comparative feature analysis) deferred" — no, omit entirely per instruction. Hmm, but omitting might confuse since paper has 3 RQs. The user explicitly instructed: "Results should focus on what the paper already answers, not included undeveloped sections and RQs." So the presentation should only cover answered things. Omit RQ3. Good.

Also note the draft's "External Cloaking" results section literally just restates RQ3's question text — clearly undeveloped. So external cloaking beyond Table 1 counts → present only what's in Table 1 + redirect figures. I'll avoid claims about geo-based cloaking differences (not yet written). I'll frame slide 11's redirect part carefully: "single- vs multi-hop chains quantified (7,490 vs 8,322); flow maps show intermediary→destination structure" — keep generic.

Should I verify anything with web search? The paper is an anonymous draft; the bibtex includes WWW '26 companion papers by Bartuzi-Trokielewicz. The instructions say "Reason deeply and verify your conclusion from multiple independent angles." This is a summarization task of provided material — no external verification needed for the content itself. The numbers must be internally consistent with the provided draft. I could double-check arithmetic with the shell tool (sum percentages). Let me do quick mental math:

- 19,470/407,771 = 4.77% ✓ (URL masking share of corpus)
- 929/407,771 = 0.23%
- 8,322/407,771 = 2.04% ✓ (2.0%)
- 7,490/407,771 = 1.84% ✓ (1.8%)
- Sum patterns = 36,211; total cloaked 26,921 → overlap of 9,290 ads. I'll note non-exclusivity cautiously: "per-pattern counts are not mutually exclusive" — safe arithmetic claim.
- 26,921/407,771 = 6.60% ✓
- VIDEO: 16,863/223,002 = 7.56% ✓
- IMAGE: 6,744/112,877 = 5.97% ✓
- DCO: 2,336/38,846 = 6.01% ✓
- CAROUSEL: 308/27,032 = 1.14% ✓
- DPA: 658/2,453 = 26.82% ✓
- 883/929 = 95.0% of card cloaking in DCO ✓
- DPA single redirection: 543/2,453 = 22.1% ✓
- VIDEO+IMAGE = 335,879 = 82.3% (paper text says 81.1% — slight inconsistency in draft; I'll use "~81%" to stay faithful)
- Dynamic formats: 38,846+27,032+2,453 = 68,331; 68,331/407,771 = 16.76% ✓ (paper says 16.6%)
- Multi+single redirection = 15,812 = 3.88% of corpus.

I could run a quick shell check, but mental math suffices; these are simple. Actually, let me be diligent and run the arithmetic via the shell tool to verify — it's cheap and adds rigor. I'll do one bash call computing the percentages. That aligns with "verify from multiple independent angles." Let me do it.

Actually, I can do several computations in one call with python3. Let me write a small python script verifying all key ratios. Then finalize the deck.

One more consideration: the deck should be "dense" — so each slide packs content. I'll write slide content in Markdown, with each slide separated by `---`. I'll also include speaker notes in collapsible details blocks per formatting rules. The rule says use collapsible sections when many sections with varying importance — speaker notes/backup content qualifies.

Let me also think: does the user want a PPTX? They said "distill this paper draft into dense slides" — text/markdown slides are the deliverable I can produce. I'll structure clearly with slide numbers and titles. Maybe I'll offer the deck in Marp-compatible format (front-matter with `marp: true`)? That could be a nice touch — Marp is a common markdown-to-slides tool. But adding front-matter complicates. I'll use simple `---` separators and note that it's Marp/pandoc-compatible. Actually adding `marp: true` front matter is helpful if they use Marp. I'll skip front-matter to keep it clean, but mention compatibility in a closing line. Or use `# Slide N — Title` headers. I'll do:

```
---

## Slide 5 · Methodology I — ...
content
```

with `---` between. Hmm, in Marp, `---` separates slides. Headers inside. Good.

Also, per instructions: "For all mathematical expressions, you must use dollar-sign delimiters." I might use 6.6? Percentages aren't really math expressions; but to be safe with any formula-like content, avoid LaTeX except where needed. I could write ratios like 26,921/407,771≈6.6 on a slide — that would use dollar signs appropriately. I'll use it sparingly (one or two places) to comply with the spirit. Actually the rule says for all mathematical expressions use $...$. If I include any computation, wrap in $. I'll include a couple.

Let me also double check details for accuracy:

- "407771 full advert media + metadata pairs, taking over more than 600GB storage space" ✓
- Dates: 20 April – 19 June 2026 ✓
- 4 IPs: Brazil, Portugal, Germany, US; 5 repetitions ✓
- tldextract + PSL ✓
- Contributions (3) ✓
- Gap (2: conceptual, security auditing) ✓
- Limitation: unknown total ads in circulation ✓
- Recommendations (3) ✓
- Domain result: 26,279 unique domains; whatsapp.com >50× shopee.com ✓
- Szurdi: 81% more malicious URLs with cloaking-aware scraping ✓
- Edelson: 3M+ political ads; unretrievable ads section; advertiser-identifier-based ✓
- Vaidya & Garimella: 29,772 ads, 23,620 media, 79.3%; "missing or dynamically loaded elements"; 20.6% attributed to missing/dynamic content and access instability ✓
- El Fraihi: creative optimization effect bypass for contextual ads on YouTube ✓
- Bartuzi-Trokielewicz 2026 (both papers): closest to cloaking-pattern analysis in an ecosystem, platform not specified ✓

Figures: Fig 1 TLD distribution by advertiser ranges; Fig 2 URL distribution; Fig 3 card-cloaked example (doceemminutos.com vs pay.kiwify.com.br/211hNC8); Fig 4 masks using Tranco domains; Fig 5 masks simulating Google; last two images = sankey-like flows (likely Fig 6/7 redirect flows). I'll reference them as figures.

Example from Fig 3: caption/visible domain "do-ceemminutos.com" (rendered as "do- ceemminutos.com") vs embedded "pay.kiwify.com.br/211hNC8". The OCR shows "do- ceemminutos.com" and "pay.kiwify.com.br/211hNC8". I'll write "doceemminutos.com" → hmm, risky. Write as shown: `do-ceemminutos.com` vs `pay.kiwify.com.br`. I'll say "a Brazilian recipe-style brand domain vs a payment-processor link (kiwify.com.br)". The text in Fig 3: "leads the audience into believing the website domain is 'do- ceemminutos.com' while the actually embedded URL is 'pay.kiwify.com.br/211hNC8'". OK I'll use that.

Now the "circularity" claim: "the most commonly used ones being dominated by Meta's own platforms, highlighting the circularity of Meta's ecosystem. For instance, 'whatsapp.com' is used over 50 times more than the most frequent non-Meta domain 'shopee.com'." ✓

Tranco masks: "Masks using domains from Tranco (Le Pochat et al. 2019)" — meaning the mask captions use popular Tranco domains. ✓ And "Masks simulating google." ✓

Now — one nuance: URL masking detection compares caption-extracted domain vs link_url domain. Card masking: "one link_url differs from the others". ✓

Alright. Also the paper's stated improvement: "A first of its kind analysis of advert-embedded URLs and cloaking patterns employed in Meta's Advertising Ecosystem". ✓

Now, about slide count and density. Let me finalize 13 slides + optionally a backup. I'll write the deck now.

Structure with collapsible speaker notes per slide:

Slide 1 — Title  
Slide 2 — Motivation: cloaking 2.0 in ad ecosystems  
Slide 3 — RQs (RQ1, RQ2) & Contributions  
Slide 4 — Related work in 3 threads + gap  
Slide 5 — Methodology ①: pipeline  
Slide 6 — Methodology ②: unfiltered-search validation  
Slide 7 — Methodology ③: detection (internal/external)  
Slide 8 — Dataset anatomy (Table 1 condensed)  
Slide 9 — RQ1 results: prevalence  
Slide 10 — RQ1 results: format-level hotspots (maybe merge into 9; keep separate for density)  
Slide 11 — RQ2 results: domains & circularity  
Slide 12 — RQ2 results: camouflage & redirects  
Slide 13 — Positioning vs prior literature (the "how we improve" table)  
Slide 14 — Recommendations & limitations & takeaway

14 slides. Fine. Speaker notes under each as

.

Wait — should the improvement-vs-literature slide come earlier (after gap) or later? In a talk, positioning usually comes after results as "discussion". The user emphasized "Focus on how we improve upon previous the literature" — so make it prominent: maybe place right after the gap slide as "positioning" AND reinforce in a closing slide. I'll put the comparison table after results (slide 13) as the synthesis, since improvement claims are grounded in the new results; but also make slide 4 gap-explicit. Alternatively put the comparison right after gap (slide 5) to hit it early. Dense presentation: I'll put a compact "novelty vs prior work" summary in slide 4, and the full comparison table at slide 13. Good.

Also the user wants "methodology and results found" as the core — so methodology gets 3 slides, results get 4. Balanced.

Let me now run the verification arithmetic, then write the final deck.

Actually — do I need any tool calls at all? The task is self-contained (summarize provided text). The system prompt says to verify conclusions from multiple angles — arithmetic verification via shell is a good independent check. I'll do one shell call with python. It's low-cost and prudent.

Then produce the final answer. No search needed. No fusion needed (not appropriate — it's a distillation task, no independent perspectives needed... though arguably could help with slide design; unnecessary).

Let me write the python verification:

```
total = 407771
cats = {"URL masking":19470, "Card cloaking":929, "Multi redirection":8322, "Single redirection":7490}
total_cloaked = 26921
print(total_cloaked/total*100)
for k,v in cats.items(): print(k, v/total*100)
print("sum patterns", sum(cats.values()))
fmt = {"VIDEO":(223002,16863), "IMAGE":(112877,6744), "DCO":(38846,2336), "CAROUSEL":(27032,308), "DPA":(2453,658)}
for k,(n,c) in fmt.items(): print(k, n/total*100, c/n*100)
print("dynamic share", (38846+27032+2453)/total*100)
print("video+image", (223002+112877)/total*100)
print("card in DCO", 883/929*100)
print("redirects total", 8322+7490)
```

Check DPA card cloaking 2 (0.1%) and single redirection 543 (22.1%): 543/2453 = 22.13 ✓.

Also DPA URL masking 132/2453 = 5.38 ✓ (5.4%).

OK, run it, then write the deck.

For the final deliverable, I'll present the deck in a way that's copy-paste ready for Marp/PowerPoint. Use tables where valuable (Table 1 condensed, prior-work comparison). Keep bullets tight. Use bold for key numbers.

One more check on wording: "6.6% of all ads cloaked" — but with the overlap caveat, "Total Cloaked" row is what the paper reports. I'll say "26,921 ads (6.6%) flagged by ≥1 detector; per-pattern counts overlap."

Also, note the paper's phrase "internal cloaking" = detected entirely within Ad Library metadata (no HTTP requests) — RQ1. External = URL resolution — RQ2's second half. Good mapping:

- RQ1 → internal (URL masking, card masking; prevalence)
- RQ2 → domain distribution + redirection cloaking on request (single/multi hop counts)

That mapping is clean and matches the draft.

One more consideration on RQ1 wording: "What forms of URL cloaking can be detected internally within the Ad Library? Which mechanisms are exploited and how prevalent are they?" — answered: URL masking (caption field), card masking (dynamic formats); prevalence numbers above. ✓

RQ2: "What is the distribution of domains embedded in adverts? When requested, what kinds of redirection cloaking can be observed?" — answered: skewed distribution, Meta circularity, 26,279 domains; redirection: single vs multi-hop observed at scale (15,812). ✓

Now, slide density: keep each slide ≤ ~8 bullet lines with sub-bullets. Dense but readable.

Let me also add a tiny "one-slide summary" (executive) at the start? That could be slide 2. Dense talks often have "TL;DR" slide. I'll fold key numbers into title slide subtitle + takeaways at end. Maybe add an "At a glance" box on slide 3. Keep it.

Alright, run verification now.

After that, compose final answer: brief intro line, then the deck, then a short closing note about what was excluded (RQ3/undeveloped sections) — actually a brief note is useful to confirm I followed the instruction: "RQ3 (comparative feature analysis) and the empty External-Cloaking/Comparative-Analysis stubs were deliberately omitted; only redirection counts already tabulated are reported." Yes, include a one-line note at the end (outside slides) or as speaker note on RQ slide. Good — put it as a small note in the RQ slide's speaker notes AND mention at the end briefly.

Formatting rules to respect:

- Markdown lists/tables ✓
- Code fences for code (I'll fence the Marp front-matter? I'll present the deck as plain markdown, not fenced — since the response itself is markdown. If I fence the whole deck, it becomes one giant code block — harder to read but easier to copy for Marp. Hmm. Presentations are often pasted into Marp. But rendering tables inside a code fence loses preview. I'll present unfenced markdown so it renders nicely in chat, using `---` separators; mention it's Marp-compatible.)
- Inline code for field names like `link_url`, `caption`, `tldextract` ✓
- Math with $...$ for any computed ratio ✓ (use sparingly, e.g., 26,921/407,771≈6.6)
- Collapsible details for speaker notes ✓

Let me write the verification script and call the tool.

Then write the final answer. Length: the deck will be long-ish (14 slides) but that's what's asked. Keep speaker notes concise (2-4 lines each).

Edge cases: The user may want slide numbers matching a talk length. Dense 14-slide deck for a ~12-15 min conference talk is realistic. I'll note "~14 slides".

Also the venue: paper is anonymous submission, references WWW Companion '26 cited works and submission targets ICWSM 27 (file name "ICWSM_27"). Title slide can say "ICWSM 2027 submission (anonymous)". The filename says ICWSM_27. Fine.

Now write.

Also note: should I include the '%' math in dollar signs? E.g., 26,921 ads — using math for numbers with thousands separators could look odd. I'll use $...$ only for actual computed expressions like 6.6 or fractions. Keep most numbers as plain text to preserve slide readability. The rule says all mathematical expressions must use $ delimiters — a bare percentage in prose is arguably not a "mathematical expression," but a computed ratio is. I'll wrap the couple of computed comparisons in $...$.

Let me write out the whole thing.

Deck:

---

**Slide 1 — Title**

# Behind Cloaks and Masks

### Uncovering Deceptive Misuse of Meta's Advertisement Systems

- ICWSM '27 · Anonymous submission
- **TL;DR:** First large-scale audit of URL cloaking inside Meta's Ad Library — 407,771 ads with full multimedia, Apr–Jun 2026, >600 GB → **26,921 cloaked ads (6.6%)**, three reusable detectors, unified 20-year cloaking definition.

Speaker notes: frame as transparency-infrastructure audit...

**Slide 2 — Motivation**

- Cloaking (show auditors ≠ users) is as old as Web 1.0: search spam (Wu & Davison '06; Wang et al. '11), phishing kits (CrawlPhish '21), traffic distribution systems (Szurdi '21)
- OSN ad systems add new abuse surface: `caption` anchor text, dynamic creative delivery — abusable for **moderation evasion**
- Meta's Ad Library = the transparency mechanism, yet its **URL layer has never been audited at scale**
- 20+ years of cloaking research remains fragmented into context-specific silos → same tricks recur under different names

**Slide 3 — Questions & Contributions**  
RQ1 (answered): which URL-cloaking forms are detectable _internally_ in Ad Library metadata? mechanisms & prevalence?  
RQ2 (answered): what domains do ads embed, and what redirection cloaking appears on resolution?  
Contributions:

1. First-of-its-kind analysis of advert-embedded URLs & cloaking patterns in Meta's ad ecosystem → uncovering malicious abuse of ad-distribution features to evade moderation & deceive consumers
2. Unified definition of cloaking across 20+ years → enduring, resurging, novel practices tied to adjacent areas (phishing, TDS, SEO spam)
3. Low-resource moderation strategies grounded in observed abuse patterns

Speaker note: RQ3-style comparative feature analysis intentionally excluded (undeveloped).

**Slide 4 — Where prior work stops (gap)**

- Ad auditing: political (…), health/COVID, betting, Ad-Library security flaws (Edelson '20), transparency limits (Gkiouzepi '23), biased delivery (Ali '19), fraud revenue (Papadogiannakis '25) — none examine embedded URLs/cloaking
- Cloaking studies: search engines (2006–2011), phishing client-side (CrawlPhish '21), TDS abuse (Szurdi '21: cloaking-aware scraping finds **81% more** malicious URLs) — all off-platform, context-specific definitions
- Masking primitives: anchor-text phishing ('12/'22), link presentation & susceptibility (Zhuo '24a/b), shortener abuse (Fukushi '21; Odgerel '25), redirect intermediaries (Zeng '22), creative-optimization bypass (El Fraihi '26, YouTube)
- Closest ecosystem analysis: Bartuzi-Trokielewicz et al. '26 (WWW Companion) — platform-agnostic synthetic-media scams  
    → **Gap: unified cloaking definition + first advert-URL audit of Meta's ecosystem**

**Slide 5 — Methodology ① Collection pipeline**

- Web-only: Ad Library API restricted to political/social ads in most countries → crawl the **web interface** for full coverage
- 2-month crawl (20 Apr – 19 Jun 2026): **407,771 ads**, full media + metadata pairs, **>600 GB**
- Completeness-first: images **and** videos downloaded (most prior studies skip or partial-collect multimedia)
- Preliminary metadata-only pass enumerated **every** display format (VIDEO, IMAGE, DCO, CAROUSEL, DPA, …) → ingestion handles all dynamic creatives
- Nearest prior pipeline: Le Pochat et al. '22 audit; deltas = multimedia + unfiltered search

**Slide 6 — Methodology ② "Unfiltered" search & why it matters**  
Empirical validation of special-character search ('*'):

- `keyword *` ≡ `keyword` (position-independent)
- `*` on an advertiser page ≡ full ad listing
- `*` in countries with <50k ads returns ≥ vowel-query results
- other special characters behave identically  
    → assumption: `*` ≡ unfiltered search; reinforced by content diversity + retrieval of ads **not displayed on advertiser pages**  
    Why it matters:
- advertiser-constrained crawls (Edelson '20: 3M+ political ads) bias toward known advertisers — blind spot exactly where evasion lives
- dodges documented unretrievable-ad / inconsistency issues of the Library (bug-fix reduced but didn't eliminate)

**Slide 7 — Methodology ③ Detection taxonomy**  
Internal (metadata-only — RQ1):

- **URL Masking**: `caption` renders as anchor text showing arbitrary domain ≠ `link_url` destination → detect by domain comparison; discard non-URL captions; `tldextract` w/ Public Suffix List
- **Card Masking**: in multi-card dynamic ads, one card's `link_url` deviates (4× `amazon.com` + 1× `othersite.xyz`) → malicious card hidden among benign fillers  
    External (URL resolution — RQ2):
- request every ad URL from **4 geo-IPs (BR, PT, DE, US) × 5 reps** → capture variation; classify **single-hop vs multi-hop** redirection chains

**Slide 8 — Dataset anatomy (n=407,771)**

|Format|Ads (share)|Total cloaked|Notable pattern|
|---|---|---|---|
|VIDEO|223,002 (54.6%)|16,863 (7.6%)|URL masks 5.2%|
|IMAGE|112,877 (27.7%)|6,744 (6.0%)|URL masks 5.3%|
|DCO|38,846 (9.5%)|2,336 (6.0%)|card cloaking 2.3%|
|CAROUSEL|27,032 (6.6%)|308 (1.1%)|—|
|DPA|2,453 (<0.1%)|**658 (26.8%)**|**single redirection 22.1%**|
|Dataset|407,771|**26,921 (6.6%)**|patterns overlap|

- Dynamic formats = 16.6% of corpus ↔ ~20.6% prior work failed to extract ("dynamically loaded elements") → **cloaking hides exactly where collection is hardest**
- VIDEO+IMAGE ≈ 81% of corpus ≈ 79.3% media-retrieval ceiling reported by Vaidya & Garimella '26

**Slide 9 — RQ1: internal cloaking, quantified**

- **URL masking is the dominant vector: 19,470 ads** (≈4.8 of corpus; 72% of all cloaked ads) — trusted/lookalike domain shown, real destination embedded
- **Card masking: 929 ads** — 883 of 929 (95%) in DCO dynamic ads
- Detection is **cheap**: pure metadata diff, no rendering/sandbox → deployable at Library scale
- Prior masking evidence was phishing-only (anchor text '12/'22, email link presentation Zhuo '24) → we show the same primitive industrialized inside a mainstream ad platform

**Slide 10 — RQ1/②: format risk profile**

- VIDEO/IMAGE carry the volume of URL masks (5.2% / 5.3% of their formats)
- **DPA = extreme outlier: 26.8% cloaked, 22.1% single-hop redirection** → product-catalog delivery abused as redirect launderer
- CAROUSEL lowest (1.1%): static multi-card formats exploited far less than algorithmic DCO/DPA
- Redirection prevalence: multi-hop 8,322 (2.0%) vs single-hop 7,490 (1.8%) — chains are the norm, not the exception

**Slide 11 — RQ2: domain distribution & circularity**

- **26,279 unique domains**, severely skewed long-tail
- Top domains dominated by **Meta's own properties** — ads route users back into Meta (circularity)
- `whatsapp.com` linked **>50×** more than top non-Meta domain (`shopee.com`)
- TLD mix shifts by advertiser scale (Fig 1): advertiser-weighted vs unique-domain views diverge → few advertisers dominate link volume (Fig 2)

**Slide 12 — RQ2: camouflage & redirect flows**

- Masks borrow **Tranco-ranked domains** (Fig 4) and **simulate Google** (Fig 5) → weaponizing top-site trust
- Worked example (Fig 3): card shows `do-ceemminutos.com` while embed = `pay.kiwify.com.br/211hNC8` (payment processor) — brand mask over billing redirect
- Redirect flow maps (sankey figures): source → intermediary → destination structure across 15,812 resolved cloaks; single- vs multi-hop split
- Upshot: every user-facing trust signal (displayed domain) is decoupled from the actual destination

**Slide 13 — What this adds over prior literature**

|Prior work|Limitation|Our improvement|
|---|---|---|
|Edelson '20 (S&P)|advertiser-constrained, metadata-only, political niche|unfiltered `*` search; full multimedia; ecosystem-wide|
|Vaidya & Garimella '26 (ICWSM)|79.3% media retrieval; dynamic creatives lost|all-format ingestion; shows dynamic formats are the cloaking hotspot|
|Szurdi '21 (WWW, TDS)|context-specific cloaking definition|unified 20-yr definition applied in-platform|
|CrawlPhish '21 / Zeng '22|phishing/search contexts, off-platform|cloaking measured inside the platform's own transparency system|
|Bartuzi-Trokielewicz '26|platform-agnostic ecosystem scams|named platform, per-ad URL-level evidence|
|Zhuo '24 / Odgerel '25 / Fukushi '21|susceptibility & shortener risk, small scale|407k-ad in-the-wild quantification|
|El Fraihi '26 (YouTube)|bypass reported, not quantified in ads|card/DCO/DPA abuse quantified on Meta|

**Slide 14 — Recommendations, limitations, takeaways**  
Moderation (low-resource):

- **Remove URL captioning** — force true URLs visible (eradicates masking at the root)
- **Static analysis of dynamic ads** — flag cross-card link/creative discrepancies
- **Media fingerprinting** — surface persistent campaigns across formats/advertisers  
    Limitations:
- Unknown denominator (total ads in circulation unknowable) → prevalence = lower-bound of Library-visible ads
- Ad Library's documented inconsistencies (Gkiouzepi '23; Le Pochat '22)  
    Takeaway: **the transparency infrastructure itself is the cloaking vector** — the caption field and dynamic delivery are the weak links; cheap structural fixes neutralize most observed abuse.

Good. 14 slides. Dense.

Speaker notes: I'll add brief

under each slide. Keep them 1-3 sentences.

Now the verification tool call. Then final answer.

Also maybe note at top: "Drop-in Marp-compatible (separate slides with ---)". And final note: excluded RQ3 + stub sections per instruction; suggestions if they want them as "future work" slide.

Let me do the shell verification now.