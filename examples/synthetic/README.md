# Synthetic ingestion, replay and recovery

This **November 2026 extension** is independently written, fictional test data.
It is separate from the historical Amazon and Parfumo analyses. It uses Python's
standard library and SQLite; it neither runs Spark nor demonstrates cloud or
distributed-system recovery.

```bash
python3 src/synthetic_batch.py \
  --products examples/synthetic/products.csv \
  --reviews examples/synthetic/reviews.csv \
  --database /tmp/fragrance-synthetic-demo.sqlite
```

Expected first run: `COMMITTED`; repeat the exact command: `ALREADY_COMMITTED`.
The content hash identifies the two input snapshots. A byte-changed input is a
different snapshot, not a CDC update to a global current-state table.

| Source | Input records | Accepted unique records | Exact duplicates | Rejected |
| --- | ---: | ---: | ---: | ---: |
| Products | 3 | 2 | 1 | 0 |
| Reviews | 7 | 3 | 1 | 3 |

The three rejected reviews have an unknown product, a rating above five, or a
missing product ID. Quarantine records retain source role, parsed CSV record
ordinal and reason. Conflicting valid duplicate keys stop the batch instead of
selecting an arbitrary row. Inputs are bounded to 1 MB per file.

The resulting joined summary has Fictional Comet with two reviews averaging
4.5, and Fictional Orbit with one review averaging 3.0. These are fictional
fixture results, not consumer findings.

For an intentional failure, choose a new empty demo database and add
`--inject-failure`. The process exits nonzero after product inserts but before
the transaction commits. Run again without that flag to recover. Identical
already-committed batches return their result before any failure injection.
The script will not adopt an unrelated nonempty SQLite database.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_synthetic_batch.py -v
```

Tests independently check exact sums/counts, duplicate replay, invalid/nonfinite
ratings, conflicting keys, failed-batch rollback, preservation of a previous
snapshot, and recovery matching a clean run. The existing large-data source
code, saved metrics and charts are unchanged.
