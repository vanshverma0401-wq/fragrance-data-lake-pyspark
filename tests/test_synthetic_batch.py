"""Behavioral checks for the separately labeled synthetic ingestion exercise."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SyntheticBatchTests(unittest.TestCase):
    def setUp(self):
        module_path = ROOT / "src" / "synthetic_batch.py"
        if not module_path.exists():
            self.fail("The synthetic batch ingestion behavior is not implemented yet")
        spec = importlib.util.spec_from_file_location("synthetic_batch", module_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = self.folder / "warehouse.sqlite"
        self.products = self.folder / "products.csv"
        self.reviews = self.folder / "reviews.csv"
        self.products.write_text("product_id,title\nP100,Fictional Comet\nP200,Fictional Orbit\nP100,Fictional Comet\n")
        self.reviews.write_text("review_id,product_id,rating\nR1,P100,5\nR2,P100,4\nR3,P200,3\nR3,P200,3\nR4,UNKNOWN,2\nR5,P100,7\nR6,,2\n")

    def run_batch(self, **kwargs):
        return self.module.ingest(self.db, self.products, self.reviews, **kwargs)

    def counts(self):
        with sqlite3.connect(self.db) as con:
            return tuple(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                         for table in ("batches", "products", "reviews", "quarantine"))

    def test_accounts_for_every_record_and_exact_join_output(self):
        result = self.run_batch()
        self.assertEqual(result["status"], "COMMITTED")
        self.assertEqual(result["products"], {"input": 3, "accepted": 2, "duplicates": 1, "rejected": 0})
        self.assertEqual(result["reviews"], {"input": 7, "accepted": 3, "duplicates": 1, "rejected": 3})
        self.assertEqual(self.counts(), (1, 2, 3, 3))
        self.assertEqual(result["summary"], [
            {"product_id": "P100", "title": "Fictional Comet", "reviews": 2, "average_rating": 4.5},
            {"product_id": "P200", "title": "Fictional Orbit", "reviews": 1, "average_rating": 3.0},
        ])

    def test_identical_replay_is_a_no_op(self):
        first = self.run_batch()
        second = self.run_batch()
        self.assertEqual(second["status"], "ALREADY_COMMITTED")
        self.assertEqual(first["batch_id"], second["batch_id"])
        self.assertEqual(first["summary"], second["summary"])
        self.assertEqual(self.counts(), (1, 2, 3, 3))

    def test_failure_rolls_back_then_retry_matches_clean_result(self):
        with self.assertRaisesRegex(RuntimeError, "injected"):
            self.run_batch(inject_failure=True)
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        recovered = self.run_batch()
        clean_db = self.folder / "clean.sqlite"
        clean = self.module.ingest(clean_db, self.products, self.reviews)
        self.assertEqual(recovered, clean)

    def test_failure_does_not_remove_previously_committed_snapshot(self):
        first = self.run_batch()
        self.reviews.write_text(self.reviews.read_text() + "R7,P200,4\n")
        with self.assertRaisesRegex(RuntimeError, "injected"):
            self.run_batch(inject_failure=True)
        self.assertEqual(self.counts(), (1, 2, 3, 3))
        second = self.run_batch()
        self.assertNotEqual(first["batch_id"], second["batch_id"])
        self.assertEqual(self.counts(), (2, 4, 7, 6))

    def test_conflicting_duplicate_key_stops_before_commit(self):
        self.products.write_text(self.products.read_text() + "P100,Conflicting title\n")
        with self.assertRaisesRegex(ValueError, "conflicting product_id"):
            self.run_batch()
        self.assertFalse(self.db.exists())

    def test_missing_columns_are_rejected_before_loading(self):
        self.reviews.write_text("review_id,product_id\nR1,P100\n")
        with self.assertRaisesRegex(ValueError, "columns"):
            self.run_batch()
        self.assertFalse(self.db.exists())

    def test_non_finite_rating_is_quarantined(self):
        self.reviews.write_text("review_id,product_id,rating\nR1,P100,NaN\n")
        result = self.run_batch()
        self.assertEqual(result["reviews"], {"input": 1, "accepted": 0, "duplicates": 0, "rejected": 1})
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT reason FROM quarantine").fetchone()[0], "invalid_rating")

    def test_unrelated_database_is_preserved(self):
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE existing_data (value TEXT)")
            con.execute("INSERT INTO existing_data VALUES ('keep this')")
        before = self.db.read_bytes()
        with self.assertRaisesRegex(ValueError, "recognized exercise database"):
            self.run_batch()
        self.assertEqual(self.db.read_bytes(), before)

    def test_conflicting_review_key_stops_before_database_creation(self):
        self.reviews.write_text(self.reviews.read_text() + "R1,P200,1\n")
        with self.assertRaisesRegex(ValueError, "conflicting review_id"):
            self.run_batch()
        self.assertFalse(self.db.exists())

    def test_malformed_records_are_accounted_for_in_quarantine(self):
        self.reviews.write_text("review_id,product_id,rating\nR1,P100,5,unexpected\nR2,P200\n")
        result = self.run_batch()
        self.assertEqual(result["reviews"], {"input": 2, "accepted": 0, "duplicates": 0, "rejected": 2})
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT reason FROM quarantine ORDER BY record_number").fetchall(),
                             [("malformed_record",), ("malformed_record",)])


if __name__ == "__main__":
    unittest.main()
