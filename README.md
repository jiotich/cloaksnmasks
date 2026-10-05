# Behind Cloaks and Masks

Research project on URLs embedded in Meta ads, URL-related cloaking signals, and differences between candidate-signal and other ads.

## Start here

- [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) — recommended research focus, evidence/status, definitions, related-work positioning, metadata plan, and next steps.
- [`paper/INTRODUCTION_DRAFT.md`](paper/INTRODUCTION_DRAFT.md) — introduction draft with placeholders for verified counts and joins.
- [`paper/SECTION_CONSOLIDATION.md`](paper/SECTION_CONSOLIDATION.md) — section map, writing/figure plan, feasibility, and stale-draft checks.
- [`analysis/README.md`](analysis/README.md) — reproducible pipeline inputs, commands, definitions, outputs, and caveats.

## Repository layout

- `analysis/pipeline.py` — consolidated RQ1/RQ2/RQ3 analysis; local-only, read-only inputs.
- `analysis/tests/` — synthetic standard-library integration tests.
- `analysis/legacy/` — original analysis scripts kept for provenance.
- `collection/legacy/` — recovered collection/database code and the prior metadata-analysis notebook.
- `data/redirection_results/` — four geolocated final-URL result files.
- `archive/` — source exports and original input bundles.
- `paper/drafts/` and `paper/latex/` — current draft and reconstructed LaTeX text/tables.
- `notes/archive/` — prior planning notes.

The full ad SQLite database and the reported 320k image-classification file are not included in this checkout. The pipeline can audit the checked-in URL probes now; full-corpus and image-label analyses require those inputs and a verified media-hash-to-ad join. Generated `analysis/output/` files are ignored by Git.

## Quick check

```bash
python -m unittest discover -s analysis/tests -v
python analysis/pipeline.py --redirections data/redirection_results --out analysis/output/probe-audit
```
