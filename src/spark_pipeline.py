#!/usr/bin/env python3
"""Sanitized PySpark reconstruction of the fragrance data-lake workflow.

Input paths are supplied at runtime and may point to local storage, S3, or any
filesystem supported by the configured Spark environment. This script never
downloads, embeds, or redistributes upstream data.
"""

from __future__ import annotations

import argparse
from functools import reduce

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amazon-meta", required=True, help="Amazon metadata JSONL path")
    parser.add_argument("--amazon-reviews", required=True, help="Amazon reviews JSONL path")
    parser.add_argument("--parfumo", required=True, help="Parfumo-derived CSV path")
    parser.add_argument("--output", required=True, help="Output root for curated and analytics data")
    parser.add_argument("--shuffle-partitions", type=int, default=96)
    return parser.parse_args()


def join_path(root: str, *parts: str) -> str:
    return "/".join([root.rstrip("/"), *(part.strip("/") for part in parts)])


def json_get(path: str):
    return F.get_json_object(F.col("raw_json"), path)


def clean_double(expression):
    return F.regexp_replace(expression, "[^0-9.]", "").cast("double")


def clean_long(expression):
    return F.regexp_replace(expression, "[^0-9]", "").cast("long")


def clean_term(expression):
    cleaned = F.lower(F.coalesce(expression.cast("string"), F.lit("")))
    cleaned = F.regexp_replace(cleaned, "fougère", "fougere")
    cleaned = F.regexp_replace(cleaned, "[\\[\\]\\{\\}\\\"']", " ")
    cleaned = F.regexp_replace(cleaned, "[^a-zA-Z\\s\\-]", " ")
    cleaned = F.regexp_replace(cleaned, "\\s+", " ")
    return F.trim(cleaned)


def read_csv(spark: SparkSession, path: str) -> DataFrame:
    return (
        spark.read.option("header", "true")
        .option("multiLine", "true")
        .option("quote", '"')
        .option("escape", '"')
        .csv(path)
    )


def write_csv(frame: DataFrame, path: str) -> None:
    frame.coalesce(1).write.mode("overwrite").option("header", "true").csv(path)


def explode_terms(frame: DataFrame, source_column: str, output_column: str) -> DataFrame:
    excluded = [
        "nan",
        "none",
        "null",
        "n a",
        "na",
        "unknown",
        "women",
        "men",
        "unisex",
        "france",
        "usa",
        "italy",
        "germany",
        "spain",
        "brazil",
        "uae",
        "sweden",
        "russia",
    ]
    return (
        frame.withColumn(
            "term_raw",
            F.explode(F.split(F.lower(F.coalesce(F.col(source_column), F.lit(""))), ",|;|\\||/")),
        )
        .withColumn(output_column, clean_term(F.col("term_raw")))
        .where(F.length(F.col(output_column)) >= 3)
        .where(~F.col(output_column).isin(excluded))
        .drop("term_raw")
    )


def validate_parfumo_columns(frame: DataFrame) -> None:
    required = {
        "Brand",
        "Name",
        "Release_Year",
        "Rating_Value",
        "Rating_Count",
        "Main_Accords",
        "Top_Notes",
        "Middle_Notes",
        "Base_Notes",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Parfumo input is missing required columns: {', '.join(missing)}")


def main() -> None:
    args = parse_args()
    spark = SparkSession.builder.appName("fragrance-data-lake-portfolio").getOrCreate()
    spark.conf.set("spark.sql.shuffle.partitions", str(args.shuffle_partitions))
    spark.conf.set("spark.sql.adaptive.enabled", "true")

    curated = join_path(args.output, "curated")
    analytics = join_path(args.output, "analytics")

    # Amazon metadata is read as text so only explicitly selected fields are parsed.
    meta_raw = spark.read.text(args.amazon_meta).withColumnRenamed("value", "raw_json")
    meta = meta_raw.select(
        json_get("$.parent_asin").alias("parent_asin"),
        json_get("$.title").alias("product_title"),
        json_get("$.store").alias("brand_store"),
        json_get("$.main_category").alias("main_category"),
        clean_double(json_get("$.average_rating")).alias("meta_avg_rating"),
        clean_long(json_get("$.rating_number")).alias("meta_rating_count"),
        F.lower(F.col("raw_json")).alias("search_text"),
    )

    include_pattern = (
        "perfume|cologne|eau de parfum|eau de toilette|edp|edt|parfum|"
        "body mist|body spray|fragrance mist|perfume oil|fragrance oil|"
        "rollerball|spray perfume|solid perfume"
    )
    exclude_pattern = (
        "foot peel|peel mask|callus|swab|cotton|blackhead|cleansing cloth|"
        "cleansing wipes|wet cleansing|wipe|wipes|shampoo|conditioner|"
        "toothpaste|mascara|foundation|nail|moisturizer|cream|soap|"
        "body wash|shower gel|hair mask|bath bomb|face mask|sheet mask|lip balm"
    )

    fragrance_meta = (
        meta.where(F.col("search_text").rlike(include_pattern))
        .where(~F.col("search_text").rlike(exclude_pattern))
        .where(F.col("parent_asin").isNotNull())
        .where(F.length(F.col("parent_asin")) > 0)
        .dropDuplicates(["parent_asin"])
        .withColumn(
            "brand_store",
            F.when(
                F.length(F.trim(F.coalesce(F.col("brand_store"), F.lit("")))) == 0,
                F.lit("Unknown"),
            ).otherwise(F.col("brand_store")),
        )
        .withColumn(
            "product_title",
            F.when(
                F.length(F.trim(F.coalesce(F.col("product_title"), F.lit("")))) == 0,
                F.lit("Unknown Product"),
            ).otherwise(F.col("product_title")),
        )
    )
    fragrance_meta.write.mode("overwrite").parquet(join_path(curated, "amazon_fragrance_products"))

    reviews_raw = spark.read.text(args.amazon_reviews).withColumnRenamed("value", "raw_json")
    reviews = (
        reviews_raw.select(
            json_get("$.parent_asin").alias("parent_asin"),
            clean_double(json_get("$.rating")).alias("rating"),
            json_get("$.title").alias("review_title"),
            json_get("$.text").alias("review_body"),
            clean_long(json_get("$.timestamp")).alias("review_timestamp"),
            json_get("$.verified_purchase").cast("boolean").alias("verified_purchase"),
            clean_long(json_get("$.helpful_vote")).alias("helpful_vote"),
        )
        .where(F.col("parent_asin").isNotNull())
    )

    fragrance_reviews = (
        reviews.join(F.broadcast(fragrance_meta), "parent_asin", "inner")
        .where(F.col("rating").isNotNull())
        .withColumn(
            "review_text",
            F.lower(
                F.concat_ws(
                    " ", F.col("review_title"), F.col("review_body"), F.col("product_title")
                )
            ),
        )
    )
    fragrance_reviews.write.mode("overwrite").parquet(join_path(curated, "amazon_fragrance_reviews"))

    parfumo_raw = read_csv(spark, args.parfumo)
    validate_parfumo_columns(parfumo_raw)
    parfumo = (
        parfumo_raw.withColumn("Release_Year", F.col("Release_Year").cast("double"))
        .withColumn("Rating_Value", F.col("Rating_Value").cast("double"))
        .withColumn("Rating_Count", F.col("Rating_Count").cast("double"))
        .where(F.col("Rating_Value").between(0, 10))
        .where(F.col("Rating_Count") > 0)
        .withColumn(
            "fragrance_key",
            F.concat_ws("||", F.col("Brand"), F.col("Name"), F.col("Release_Year").cast("string")),
        )
    )
    parfumo.write.mode("overwrite").parquet(join_path(curated, "parfumo_cleaned"))

    brand_quality = (
        parfumo.where(F.col("Brand").isNotNull())
        .groupBy("Brand")
        .agg(
            F.count("*").alias("fragrance_count"),
            F.sum("Rating_Count").alias("total_rating_count"),
            (
                F.sum(F.col("Rating_Value") * F.col("Rating_Count"))
                / F.sum("Rating_Count")
            ).alias("weighted_rating"),
        )
        .where(F.col("fragrance_count") >= 15)
        .where(F.col("total_rating_count") >= 300)
        .withColumn("weighted_rating", F.round("weighted_rating", 3))
        .withColumn(
            "brand_score", F.round(F.col("weighted_rating") * F.log10(F.col("total_rating_count")), 3)
        )
        .orderBy(F.desc("brand_score"))
    )
    write_csv(brand_quality, join_path(analytics, "brand_quality_support"))

    accords = explode_terms(parfumo, "Main_Accords", "accord").where(
        F.col("Release_Year").between(2000, 2024)
    )
    accords_period = accords.withColumn(
        "period",
        F.when(F.col("Release_Year") >= 2018, F.lit("recent_2018_2024")).otherwise(
            F.lit("older_2000_2017")
        ),
    )
    accord_counts = accords_period.groupBy("period", "accord").agg(F.count("*").alias("accord_count"))
    period_totals = accord_counts.groupBy("period").agg(F.sum("accord_count").alias("period_total"))
    accord_shares = accord_counts.join(period_totals, "period").withColumn(
        "share", F.col("accord_count") / F.col("period_total")
    )
    recent = accord_shares.where(F.col("period") == "recent_2018_2024").select(
        "accord", F.col("accord_count").alias("recent_count"), F.col("share").alias("recent_share")
    )
    older = accord_shares.where(F.col("period") == "older_2000_2017").select(
        "accord", F.col("accord_count").alias("older_count"), F.col("share").alias("older_share")
    )
    shift = (
        recent.join(older, "accord", "inner")
        .where(F.col("recent_count") >= 80)
        .where(F.col("older_count") >= 80)
        .withColumn("share_change", F.col("recent_share") - F.col("older_share"))
        .withColumn("lift", F.col("recent_share") / F.col("older_share"))
        .where(F.col("share_change") > 0)
        .select(
            "accord",
            "older_count",
            "recent_count",
            F.round("older_share", 6).alias("older_share"),
            F.round("recent_share", 6).alias("recent_share"),
            F.round("share_change", 6).alias("share_change"),
            F.round("lift", 3).alias("lift"),
        )
        .orderBy(F.desc("share_change"), F.desc("lift"))
    )
    write_csv(shift, join_path(analytics, "recent_accord_shift"))

    selected_accords = ["sweet", "floral", "spicy", "woody", "fresh", "creamy", "leathery", "smoky"]
    trend_accords = accords.where(F.col("Release_Year").between(2010, 2024)).withColumn(
        "year", F.col("Release_Year").cast("int")
    )
    trend_counts = (
        trend_accords.where(F.col("accord").isin(selected_accords))
        .groupBy("year", "accord")
        .agg(F.count("*").alias("accord_count"))
    )
    year_totals = trend_accords.groupBy("year").agg(F.count("*").alias("year_total"))
    trends = (
        trend_counts.join(year_totals, "year")
        .withColumn("share", F.col("accord_count") / F.col("year_total"))
        .select("year", "accord", "accord_count", "year_total", F.round("share", 6).alias("share"))
        .orderBy("year", "accord")
    )
    write_csv(trends, join_path(analytics, "accord_trends_2010_2024"))

    top_brand_names = [row["Brand"] for row in brand_quality.limit(5).select("Brand").collect()]
    rank_window = Window.partitionBy("Brand").orderBy(F.desc("Rating_Value"), F.desc("Rating_Count"))
    top_perfumes = (
        parfumo.where(F.col("Brand").isin(top_brand_names))
        .where(F.col("Rating_Count") >= 25)
        .withColumn("rank", F.row_number().over(rank_window))
        .where(F.col("rank") <= 3)
        .select(
            "Brand",
            F.col("rank").alias("Rank"),
            F.col("Name").alias("Perfume"),
            F.round("Rating_Value", 2).alias("Rating"),
            F.col("Rating_Count").cast("long").alias("Rating_Count"),
        )
        .orderBy("Brand", "Rank")
    )
    write_csv(top_perfumes, join_path(analytics, "top_perfumes_from_strong_brands"))

    note_frames = [
        explode_terms(parfumo, column, "note").select(
            "fragrance_key", "Rating_Value", "Rating_Count", "note"
        )
        for column in ["Top_Notes", "Middle_Notes", "Base_Notes"]
    ]
    notes_all = reduce(lambda left, right: left.unionByName(right), note_frames).dropDuplicates(
        ["fragrance_key", "note"]
    )
    notes_high = notes_all.where((F.col("Rating_Value") >= 8.0) & (F.col("Rating_Count") >= 25))
    total_all = parfumo.select("fragrance_key").distinct().count()
    total_high = (
        parfumo.where((F.col("Rating_Value") >= 8.0) & (F.col("Rating_Count") >= 25))
        .select("fragrance_key")
        .distinct()
        .count()
    )
    note_all_counts = notes_all.groupBy("note").agg(F.countDistinct("fragrance_key").alias("all_count"))
    note_high_counts = notes_high.groupBy("note").agg(
        F.countDistinct("fragrance_key").alias("high_count")
    )
    note_lift = (
        note_all_counts.join(note_high_counts, "note", "inner")
        .where(F.col("all_count") >= 200)
        .where(F.col("high_count") >= 25)
        .withColumn("base_rate", F.col("all_count") / F.lit(total_all))
        .withColumn("high_rate", F.col("high_count") / F.lit(total_high))
        .withColumn("lift", F.col("high_rate") / F.col("base_rate"))
        .select(
            "note",
            "all_count",
            "high_count",
            F.round("base_rate", 6).alias("base_rate"),
            F.round("high_rate", 6).alias("high_rate"),
            F.round("lift", 3).alias("lift"),
        )
        .orderBy(F.desc("lift"), F.desc("high_count"))
    )
    write_csv(note_lift, join_path(analytics, "high_rated_note_lift"))

    metrics = [
        ("amazon_metadata_raw_rows", meta_raw.count()),
        ("amazon_fragrance_products_after_filter", fragrance_meta.count()),
        ("amazon_review_rows_parsed", reviews.count()),
        ("amazon_fragrance_review_rows_after_join", fragrance_reviews.count()),
        ("parfumo_cleaned_rows", parfumo.count()),
        ("brand_quality_rows", brand_quality.count()),
        ("recent_accord_shift_rows", shift.count()),
        ("accord_trend_rows", trends.count()),
        ("top_perfume_rows", top_perfumes.count()),
        ("high_rated_note_lift_rows", note_lift.count()),
    ]
    write_csv(spark.createDataFrame(metrics, ["metric", "value"]), join_path(analytics, "quality_summary"))
    spark.stop()


if __name__ == "__main__":
    main()

