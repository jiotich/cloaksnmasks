"""Small deterministic integration checks for the standard-library pipeline."""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analysis import pipeline  # noqa: E402


class PipelineIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "ads.sqlite"
        self.probes = self.root / "probes"
        self.probes.mkdir()
        self.out = self.root / "out"
        self.labels = self.root / "labels.csv"
        self._make_db()
        self._make_inputs()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_db(self) -> None:
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE advert (
                ad_archive_id TEXT PRIMARY KEY,
                advertiser_id TEXT NOT NULL,
                display_format TEXT NOT NULL,
                metadata TEXT NOT NULL
            );
            CREATE TABLE ad_media (
                hash TEXT NOT NULL,
                ad_archive_id TEXT NOT NULL,
                url_filename TEXT NOT NULL
            );
        """)
        ads = [
            (
                "a1", "p1", "IMAGE", {
                    "page_id": "p1", "publisher_platform": ["FACEBOOK", "INSTAGRAM"],
                    "start_date": "2026-01-01", "end_date": "2026-01-08",
                    "total_active_time": 604800,
                    "snapshot": {
                        "display_format": "IMAGE", "cta_type": "SHOP_NOW",
                        "page_categories": ["Retail"], "page_entity_type": "BUSINESS",
                        "caption": "See offers at https://masked.example/path",
                        "link_url": "https://landing.example/path?campaign=1",
                        "body": "Buy today", "title": "Offer",
                    },
                },
            ),
            (
                "a2", "p2", "IMAGE", {
                    "page_id": "p2", "publisher_platform": ["FACEBOOK"],
                    "snapshot": {
                        "display_format": "IMAGE", "cta_type": "LEARN_MORE",
                        "page_categories": ["Retail"], "page_entity_type": "BUSINESS",
                        "caption": "plain.example", "link_url": "https://plain.example/path",
                    },
                },
            ),
            (
                "a3", "p3", "DPA", {
                    "page_id": "p3", "publisher_platform": [],
                    "snapshot": {
                        "display_format": "DPA", "cta_type": "SHOP_NOW",
                        "page_categories": ["Beauty", "Retail"], "page_entity_type": "CREATOR",
                        "cards": [
                            {"link_url": "https://first.example/item", "caption": "first.example"},
                            {"link_url": "https://second.example/item", "caption": "second.example"},
                        ],
                    },
                },
            ),
            (
                "a4", "p4", "TEXT", {
                    "page_id": "p4", "snapshot": {"display_format": "TEXT"},
                },
            ),
        ]
        for ad_id, owner, fmt, metadata in ads:
            conn.execute(
                "INSERT INTO advert VALUES (?, ?, ?, ?)",
                (ad_id, owner, fmt, json.dumps(metadata)),
            )
        for media_hash, ad_id in (("h1", "a1"), ("h2", "a2"), ("h3", "a3")):
            conn.execute("INSERT INTO ad_media VALUES (?, ?, ?)", (media_hash, ad_id, media_hash + ".jpg"))
        conn.commit()
        conn.close()

    def _make_inputs(self) -> None:
        requested = "https://landing.example/path?campaign=1"
        br = {
            "metadata": {"total": 2, "errors": 0, "completed": True},
            requested: ["https://redirector.example/final", "Errored out"],
            "https://plain.example/path": ["https://shop.example/final"],
        }
        us = {
            "metadata": {"total": 2, "errors": 0, "completed": True},
            requested: ["https://another-final.example/final"],
            "https://plain.example/path": ["https://shop.example/final"],
        }
        (self.probes / "brasil.json").write_text(json.dumps(br), encoding="utf-8")
        (self.probes / "eua.json").write_text(json.dumps(us), encoding="utf-8")
        with self.labels.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["media_hash", "label"])
            writer.writeheader()
            writer.writerows([
                {"media_hash": "h1", "label": "food"},
                {"media_hash": "h2", "label": "food"},
                {"media_hash": "h3", "label": "beauty"},
            ])

    def test_full_pipeline_outputs_and_field_coverage(self) -> None:
        url_results, diagnostics = pipeline.load_redirection_results(self.probes)
        self.assertEqual(diagnostics["canonical_requested_urls_union"], 2)
        self.assertEqual(diagnostics["canonical_requested_urls_intersection"], 2)
        summaries, legacy, edges, country_rows, legacy_rows = pipeline.summarize_redirections(url_results)
        exact_key = pipeline.canonical_url("https://landing.example/path?campaign=1")
        self.assertEqual(summaries[exact_key]["status"], "multiple_destinations")
        self.assertEqual(summaries[exact_key]["error_observations"], 1)
        self.assertTrue(summaries[exact_key]["country_outcomes_differ"])
        ordinary_redirect = summaries[pipeline.canonical_url("https://plain.example/path")]
        self.assertEqual(ordinary_redirect["status"], "single_external_destination")
        self.assertEqual(len(edges), 4)

        conn = pipeline._read_only_sqlite(self.db)
        asset_to_ads, _ = pipeline.load_media_associations(conn)
        conn.close()
        label_data = pipeline.load_image_labels(self.labels, asset_to_ads)
        self.assertEqual(label_data["diagnostics"]["matched_assets"], 3)
        self.assertEqual(label_data["labels_by_ad"]["a1"], {"food"})

        result = pipeline.analyze_database(
            self.db, self.out,
            url_results=url_results,
            url_summaries=summaries,
            legacy_domain_status=legacy,
            image_labels=label_data,
            tranco_ranks={},
            limit=None,
            include_sensitive_urls=False,
            minimum_positive_cell=1,
        )
        self.assertEqual(result["ads_scanned"], 4)
        self.assertEqual(result["ads_with_url"], 3)
        self.assertEqual(result["unique_registered_domains"], 4)
        self.assertEqual(result["labelled_ads_matched"], 3)

        with (self.out / "ad_inventory.csv").open(newline="", encoding="utf-8") as stream:
            ads = {row["ad_archive_id"]: row for row in csv.DictReader(stream)}
        self.assertEqual(ads["a1"]["page_categories"], "Retail")
        self.assertEqual(float(ads["a1"]["active_lifetime_days"]), 7.0)
        self.assertEqual(ads["a1"]["image_labels"], "food")
        self.assertEqual(ads["a2"]["single_external_destination_url"], "True")
        self.assertEqual(ads["a2"]["any_cloaking_url_scope"], "False")
        self.assertEqual(ads["a3"]["card_domain_heterogeneity_candidate"], "True")
        self.assertEqual(ads["a4"]["image_labels"], "")

        with (self.out / "format_pattern_summary.csv").open(newline="", encoding="utf-8") as stream:
            format_reader = csv.DictReader(stream)
            format_rows = list(format_reader)
            self.assertIn("single_external_destination_url_ads", format_reader.fieldnames or [])
            self.assertIn("multiple_destinations_url_candidate_ads", format_reader.fieldnames or [])
            image_row = next(row for row in format_rows if row["display_format"] == "IMAGE")
            self.assertEqual(image_row["single_external_destination_url_ads"], "1")

        with (self.out / "metadata_field_availability.csv").open(newline="", encoding="utf-8") as stream:
            fields = {row["field"]: row for row in csv.DictReader(stream)}
        self.assertEqual(fields["publisher_platform"]["non_missing_ads"], "2")
        self.assertEqual(fields["start_date"]["non_missing_ads"], "1")
        self.assertEqual(fields["derived_active_lifetime_days"]["non_missing_ads"], "1")

        with (self.out / "rq3_categorical_comparisons.csv").open(newline="", encoding="utf-8") as stream:
            comparisons = list(csv.DictReader(stream))
        self.assertTrue(any(row["feature"] == "image_label" and row["category"] == "food" for row in comparisons))
        self.assertTrue(any(row["feature"] == "page_category" and row["category"] == "Beauty" for row in comparisons))
        self.assertTrue((self.out / "domain_frequency_cdf.csv").exists())
        self.assertTrue((self.out / "image_label_assets.csv").exists())
        with (self.out / "url_inventory.csv").open(newline="", encoding="utf-8") as stream:
            url_reader = csv.DictReader(stream)
            self.assertNotIn("raw_link_url", url_reader.fieldnames or [])

    def test_domain_parser_and_lifetime_helpers(self) -> None:
        self.assertEqual(pipeline.domain_parts("shop.example.co.uk")[0], "example.co.uk")
        self.assertEqual(pipeline.caption_domain("Visit https://masked.example/page today"), "masked.example")
        self.assertEqual(pipeline._active_lifetime_days("2026-01-01", "2026-01-08"), 7.0)
        self.assertIsNone(pipeline._active_lifetime_days("2026-02-01", "2026-01-01"))


if __name__ == "__main__":
    unittest.main()
