#!/usr/bin/env python3
"""Small, fictional SQLite ingestion/replay exercise; not the Spark reconstruction."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sqlite3
from pathlib import Path


APPLICATION_ID = 0x46524731
MAX_INPUT_BYTES = 1_000_000


def _read(path: Path, required: set[str]):
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("This bounded exercise accepts at most 1 MB per input")
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Input exceeded the exercise size limit")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if set(reader.fieldnames or []) != required or len(reader.fieldnames or []) != len(required):
        raise ValueError(f"Expected columns: {', '.join(sorted(required))}")
    return raw, list(reader)


def _prepare(products: Path, reviews: Path):
    product_bytes, product_rows = _read(products, {"product_id", "title"})
    review_bytes, review_rows = _read(reviews, {"review_id", "product_id", "rating"})
    digest = hashlib.sha256()
    for label, raw in ((b"products", product_bytes), (b"reviews", review_bytes)):
        digest.update(label + len(raw).to_bytes(8, "big") + raw)
    batch_id = digest.hexdigest()
    accepted_products, accepted_reviews, issues = {}, {}, []
    counts = {"products": {"input": len(product_rows), "accepted": 0, "duplicates": 0, "rejected": 0},
              "reviews": {"input": len(review_rows), "accepted": 0, "duplicates": 0, "rejected": 0}}

    def reject(kind, number, reason):
        counts[kind]["rejected"] += 1
        issues.append((kind + ".csv", number, reason))

    for number, row in enumerate(product_rows, 1):
        if None in row or any(value is None for value in row.values()):
            reject("products", number, "malformed_record")
            continue
        key, title = row["product_id"].strip(), row["title"].strip()
        if not key or not title:
            reject("products", number, "missing_product_field")
        elif key in accepted_products:
            if accepted_products[key] != title:
                raise ValueError("conflicting product_id in snapshot")
            counts["products"]["duplicates"] += 1
        else:
            accepted_products[key] = title

    for number, row in enumerate(review_rows, 1):
        if None in row or any(value is None for value in row.values()):
            reject("reviews", number, "malformed_record")
            continue
        key, product = row["review_id"].strip(), row["product_id"].strip()
        if not key or not product:
            reject("reviews", number, "missing_review_field")
            continue
        try:
            rating = float(row["rating"])
        except ValueError:
            rating = float("nan")
        if not math.isfinite(rating) or not 1 <= rating <= 5:
            reject("reviews", number, "invalid_rating")
        elif product not in accepted_products:
            reject("reviews", number, "unknown_product")
        elif key in accepted_reviews:
            if accepted_reviews[key] != (product, rating):
                raise ValueError("conflicting review_id in snapshot")
            counts["reviews"]["duplicates"] += 1
        else:
            accepted_reviews[key] = (product, rating)
    counts["products"]["accepted"] = len(accepted_products)
    counts["reviews"]["accepted"] = len(accepted_reviews)
    for group in counts.values():
        assert group["input"] == group["accepted"] + group["duplicates"] + group["rejected"]
    return batch_id, counts, accepted_products, accepted_reviews, issues


def ingest(database: Path, products: Path, reviews: Path, *, inject_failure=False):
    """Atomically commit one content-addressed snapshot, or return its existing result.

    Changed input is another snapshot, not a CDC upsert or a production watermark.
    The failure switch deliberately aborts after product inserts and before commit.
    """
    batch_id, counts, product_rows, review_rows, issues = _prepare(Path(products), Path(reviews))
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(database)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        application_id = con.execute("PRAGMA application_id").fetchone()[0]
        tables = con.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        if application_id not in (0, APPLICATION_ID) or (application_id == 0 and tables):
            raise ValueError("Database is not an empty or recognized exercise database")
        con.executescript(f"""
            PRAGMA application_id = {APPLICATION_ID};
            CREATE TABLE IF NOT EXISTS batches (batch_id TEXT PRIMARY KEY, counts_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS products (
                batch_id TEXT, product_id TEXT, title TEXT NOT NULL,
                PRIMARY KEY (batch_id, product_id), FOREIGN KEY (batch_id) REFERENCES batches);
            CREATE TABLE IF NOT EXISTS reviews (
                batch_id TEXT, review_id TEXT, product_id TEXT NOT NULL, rating REAL NOT NULL CHECK(rating BETWEEN 1 AND 5),
                PRIMARY KEY (batch_id, review_id),
                FOREIGN KEY (batch_id, product_id) REFERENCES products(batch_id, product_id));
            CREATE TABLE IF NOT EXISTS quarantine (
                batch_id TEXT, source_file TEXT, record_number INTEGER, reason TEXT NOT NULL,
                PRIMARY KEY (batch_id, source_file, record_number), FOREIGN KEY (batch_id) REFERENCES batches);
        """)
        existing = con.execute("SELECT counts_json FROM batches WHERE batch_id = ?", (batch_id,)).fetchone()
        if existing:
            counts = json.loads(existing[0])
            status = "ALREADY_COMMITTED"
        else:
            with con:
                con.execute("INSERT INTO batches VALUES (?, ?)", (batch_id, json.dumps(counts, sort_keys=True)))
                con.executemany("INSERT INTO products VALUES (?, ?, ?)",
                                [(batch_id, key, title) for key, title in sorted(product_rows.items())])
                if inject_failure:
                    raise RuntimeError("injected failure before batch commit")
                con.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?)",
                                [(batch_id, key, product, rating) for key, (product, rating) in sorted(review_rows.items())])
                con.executemany("INSERT INTO quarantine VALUES (?, ?, ?, ?)",
                                [(batch_id, *issue) for issue in issues])
            status = "COMMITTED"
        rows = con.execute("""
            SELECT p.product_id, p.title, COUNT(r.review_id), AVG(r.rating)
            FROM products p LEFT JOIN reviews r
              ON r.batch_id = p.batch_id AND r.product_id = p.product_id
            WHERE p.batch_id = ? GROUP BY p.product_id, p.title ORDER BY p.product_id
        """, (batch_id,)).fetchall()
        return {"batch_id": batch_id, "status": status, **counts,
                "summary": [{"product_id": key, "title": title, "reviews": count, "average_rating": avg}
                            for key, title, count, avg in rows]}
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products", required=True, type=Path)
    parser.add_argument("--reviews", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--inject-failure", action="store_true", help="abort a new batch before commit")
    args = parser.parse_args()
    try:
        result = ingest(args.database, args.products, args.reviews, inject_failure=args.inject_failure)
    except (ValueError, RuntimeError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Batch not committed: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
