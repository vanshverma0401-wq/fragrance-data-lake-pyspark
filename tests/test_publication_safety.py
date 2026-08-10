from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def text_files() -> list[Path]:
    allowed = {".md", ".py", ".txt", ".csv", ".gitignore"}
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in allowed
        and path.name != "test_publication_safety.py"
    )


def test_no_secret_or_private_identifier_patterns() -> None:
    patterns = {
        "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
        "cloud_storage_uri": re.compile(r"\bs3://[^\s`]+", re.IGNORECASE),
        "emr_cluster_or_step_id": re.compile(r"\b[JS]-[A-Z0-9-]{6,}\b", re.IGNORECASE),
        "aws_account_id": re.compile(r"(?<!\d)\d{12}(?!\d)"),
        "local_home_path": re.compile(r"/(?:Users|home)/[^\s`]+"),
        "private_course_token": re.compile(r"\bSEIS\s*[-_]?\s*745\b", re.IGNORECASE),
    }
    findings: list[str] = []
    for path in text_files():
        content = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in patterns.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
    assert not findings, findings


def test_forbidden_files_and_private_artifacts_are_absent() -> None:
    forbidden_names = {
        "kaggle.json",
        "bucket_name.txt",
        "cluster_id.txt",
        "step_id.txt",
        "paper.pdf",
    }
    forbidden_suffixes = {".parquet", ".jsonl", ".ppt", ".pptx", ".doc", ".docx"}
    files = [path for path in ROOT.rglob("*") if path.is_file()]
    assert not [path for path in files if path.name.lower() in forbidden_names]
    assert not [path for path in files if path.suffix.lower() in forbidden_suffixes]
    assert not [path for path in files if "screenshot" in path.name.lower() or "proof" in path.name.lower()]


def test_no_oversized_files() -> None:
    files = [path for path in ROOT.rglob("*") if path.is_file()]
    assert all(path.stat().st_size < 5_000_000 for path in files)
