# Methods and limitations

## Analytical branches

The private execution used two distinct branches that must not be conflated:

1. **Amazon scale branch:** parsed Amazon Reviews'23 Beauty and Personal Care
   metadata and reviews, filtered fragrance products, then inner-joined reviews
   on `parent_asin`. This branch demonstrates data-engineering scale.
2. **Parfumo aggregate branch:** cleaned fragrance metadata and calculated the
   brand, accord, trend, and note tables used in the portfolio visuals.

The displayed findings were not calculated from Amazon review text.

## Amazon filtering and join

- Metadata and reviews were read as text, then selected JSON fields were parsed
  explicitly to avoid nested duplicate-field issues.
- Product text was matched against fragrance terms and screened against a
  conservative list of unrelated beauty-product terms.
- Products were deduplicated by `parent_asin` before the review join.
- Reviews with a missing product key or rating were excluded.
- The final review table was produced with an inner join to the filtered product
  set. The 1,248,393 count is therefore a joined-row count, not the number of
  unique products or reviewers.

## Brand quality and support

For each brand with at least 15 fragrances and 300 total rating observations:

```text
weighted_rating = sum(rating_value * rating_count) / sum(rating_count)
brand_score = weighted_rating * log10(total_rating_count)
```

The chart displays the ten brands selected by `brand_score`, then reports their
weighted ratings and support. The score is a transparent ranking heuristic, not
a validated measure of brand quality.

## Accord shifts

- Older period: 2000–2017
- Recent period: 2018–2024
- Terms required at least 80 observations in both periods.
- `share_change = recent_share - older_share`
- `lift = recent_share / older_share`

Shares use accord observations as the denominator. A fragrance can contribute
multiple accords, so the values should not be described as the percentage of
perfumes or consumers.

## Accord trends

The trend table covers 2010–2024 and eight selected accords. For each year:

```text
share = accord_count / all_accord_observations_in_year
```

The visualization shows six series to keep the chart legible; the complete
eight-accord aggregate table remains available under `data/derived`.

## High-rated note lift

The high-rated subset contains fragrances with a rating of at least 8.0 and at
least 25 ratings. Note rows were deduplicated per fragrance. Eligible notes
required at least 200 occurrences overall and at least 25 in the high-rated
subset.

```text
base_rate = fragrances_with_note / all_cleaned_fragrances
high_rate = high_rated_fragrances_with_note / all_high_rated_fragrances
lift = high_rate / base_rate
```

## Validation performed

- reconciled 12 saved pipeline metrics with the private report
- checked brand thresholds, uniqueness, and score arithmetic
- checked accord-shift share and lift arithmetic
- checked trend grain, year range, and share arithmetic
- checked note-lift thresholds, uniqueness, and arithmetic
- confirmed duplicate output aliases and the private proof copy by SHA-256
- rebuilt public charts from aggregate tables rather than private screenshots

## Limitations

- The raw datasets are not stored locally in this public candidate, so the full
  Spark run was not repeated during portfolio reconstruction.
- Exact row counts describe one saved execution and may change if upstream data
  or filtering logic changes.
- Keyword-based Amazon product filtering can include false positives or miss
  products with unusual descriptions.
- Ratings are observational and subject to selection, popularity, platform,
  catalog, and survivorship biases.
- Accord and note text is inconsistent across records; normalization cannot
  eliminate all aliases or parsing errors.
- Brand score, time-period boundaries, and support thresholds are analyst
  choices, not universal definitions.
- No result should be treated as causal, predictive, or a purchasing
  recommendation.

