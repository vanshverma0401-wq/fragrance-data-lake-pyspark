from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived"


def test_saved_pipeline_metrics_match_verified_execution() -> None:
    frame = pd.read_csv(DATA / "pipeline_metrics.csv")
    observed = dict(zip(frame["metric"], frame["value"]))
    expected = {
        "amazon_metadata_raw_rows": 1_028_914,
        "amazon_fragrance_products_after_filter": 57_428,
        "amazon_review_rows_parsed": 23_911_390,
        "amazon_fragrance_review_rows_after_join": 1_248_393,
        "fragrantica_cleaned_rows": 24_063,
        "fragrantica_perfumes_rows": 70_103,
        "parfumo_cleaned_rows": 30_046,
        "brand_quality_rows": 420,
        "recent_accord_shift_rows": 10,
        "accord_trend_rows": 120,
        "top_perfume_rows": 15,
        "high_rated_note_lift_rows": 127,
    }
    assert observed == expected


def test_brand_result_contract() -> None:
    frame = pd.read_csv(DATA / "brand_top10.csv")
    expected = frame["weighted_rating"] * frame["total_rating_count"].map(math.log10)
    assert len(frame) == 10
    assert frame["Brand"].is_unique
    assert (frame["fragrance_count"] >= 15).all()
    assert (frame["total_rating_count"] >= 300).all()
    assert (frame["weighted_rating"].between(0, 10)).all()
    assert ((frame["brand_score"] - expected).abs() < 0.006).all()


def test_accord_shift_contract() -> None:
    frame = pd.read_csv(DATA / "accord_shift.csv")
    assert len(frame) == 10
    assert frame["accord"].is_unique
    assert (frame[["older_count", "recent_count"]] >= 80).all().all()
    assert (frame["share_change"] > 0).all()
    assert ((frame["share_change"] - (frame["recent_share"] - frame["older_share"])).abs() < 2e-6).all()
    assert ((frame["lift"] - (frame["recent_share"] / frame["older_share"])).abs() < 0.002).all()


def test_accord_trend_contract() -> None:
    frame = pd.read_csv(DATA / "accord_trends.csv")
    assert len(frame) == 120
    assert frame[["year", "accord"]].duplicated().sum() == 0
    assert (frame["year"].min(), frame["year"].max()) == (2010, 2024)
    assert frame["accord"].nunique() == 8
    expected = frame["accord_count"] / frame["year_total"]
    assert ((frame["share"] - expected).abs() < 2e-6).all()


def test_note_lift_contract() -> None:
    frame = pd.read_csv(DATA / "note_lift_top10.csv")
    assert len(frame) == 10
    assert frame["note"].is_unique
    assert (frame["all_count"] >= 200).all()
    assert (frame["high_count"] >= 25).all()
    assert ((frame["lift"] - (frame["high_rate"] / frame["base_rate"])).abs() < 0.002).all()


def test_four_public_visuals_exist() -> None:
    expected = {
        "brand_rating_support.png",
        "recent_accord_shift.png",
        "accord_trends.png",
        "high_rated_note_lift.png",
    }
    assert {path.name for path in (ROOT / "assets").glob("*.png")} == expected
    assert all((ROOT / "assets" / name).stat().st_size > 50_000 for name in expected)

