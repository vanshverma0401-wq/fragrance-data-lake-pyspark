# Data provenance and usage boundaries

This repository intentionally excludes raw records. It provides acquisition
references, a sanitized processing script, and a small set of aggregate tables
needed to verify the displayed calculations.

## Amazon Reviews'23

- Official project page: <https://amazon-reviews-2023.github.io/main.html>
- McAuley Lab dataset page: <https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023>
- Licensing discussion: <https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/discussions/1>

The dataset maintainers state that they are not in a position to assign a
license and that the data is made available primarily for research purposes.
Accordingly, this repository includes no Amazon rows, samples, cache, or
automated downloader. A user must independently determine whether their planned
use complies with the dataset terms and applicable law.

## Parfumo-derived analysis branch

- TidyTuesday data note: <https://github.com/rfordatascience/tidytuesday/blob/main/data/2024/2024-12-10/readme.md>
- TidyTuesday repository license: <https://github.com/rfordatascience/tidytuesday/blob/main/LICENSE>

The public aggregate charts were calculated from the Parfumo-derived branch of
the private execution. The TidyTuesday materials encourage analysis and sharing
while cautioning against causal conclusions. The source ultimately traces to
Parfumo data collected by a third party, so this candidate includes only small
aggregate result tables—not raw fragrance records.

The aggregate tables are included for transparency and verification. Their
presence does not grant rights to the upstream raw data, service content,
trademarks, or product descriptions.

## Fragrantica branch

- Dataset page: <https://www.kaggle.com/datasets/olgagmiufana1/fragrantica-com-fragrance-dataset>

The private workflow ingested Fragrantica files as part of its curation work,
but they did not power the findings shown in this candidate. No raw rows,
derived visualizations, credentials, or downloader for that source are
included. Consult the dataset page and its CC BY-NC-SA 4.0 terms before any use.

## Security and privacy boundary

Never commit any of the following:

- cloud credentials, access keys, session tokens, or `.env` files
- account, bucket, cluster, or job identifiers
- Kaggle credential files
- execution proofs, screenshots, or logs containing infrastructure details
- personal data, course materials, instructor content, or restricted datasets

The public script reads only paths provided at runtime and contains no stored
identifier or credential.

