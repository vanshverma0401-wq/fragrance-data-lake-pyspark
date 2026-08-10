#!/usr/bin/env python3
"""Rebuild the public aggregate charts deterministically."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived"
ASSETS = ROOT / "assets"

NAVY = "#17324D"
BLUE = "#2F6B9A"
LIGHT_BLUE = "#74A9CF"
ORANGE = "#E8812D"
GOLD = "#E7B34C"
TEAL = "#2A9D8F"
RED = "#C6534C"
PURPLE = "#7A6FAC"
INK = "#17212B"
MUTED = "#586675"
GRID = "#D9E0E6"
BG = "#F7F9FB"


def configure() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 20,
            "axes.titleweight": "bold",
            "axes.labelsize": 12,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": INK,
            "text.color": INK,
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "savefig.facecolor": BG,
        }
    )


def save(fig: plt.Figure, filename: str) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    fig.savefig(ASSETS / filename, dpi=180, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)


def footer(fig: plt.Figure, text: str) -> None:
    fig.text(0.01, 0.012, text, fontsize=8.5, color=MUTED, ha="left")


def brand_chart() -> None:
    frame = pd.read_csv(DATA / "brand_top10.csv").sort_values("brand_score")
    fig, ax = plt.subplots(figsize=(13.5, 8.2))
    y = range(len(frame))
    sizes = 190 + 760 * (frame["total_rating_count"] / frame["total_rating_count"].max())

    ax.hlines(y, 0, frame["weighted_rating"], color=LIGHT_BLUE, linewidth=5, alpha=0.55)
    ax.scatter(
        frame["weighted_rating"],
        y,
        s=sizes,
        color=BLUE,
        edgecolor="white",
        linewidth=1.8,
        zorder=3,
    )
    for position, (_, row) in enumerate(frame.iterrows()):
        ax.text(
            row["weighted_rating"] + 0.16,
            position,
            f"{row['weighted_rating']:.2f}  |  {int(row['total_rating_count']):,} ratings",
            va="center",
            fontsize=10.5,
            color=INK,
        )

    ax.set_yticks(list(y), frame["Brand"])
    ax.set_xlim(0, 10)
    ax.set_xlabel("Weighted rating (0–10)")
    ax.set_title("High-rated brands also carried substantial rating support", loc="left", pad=28)
    ax.text(
        0,
        1.02,
        "Top 10 selected by rating × log₁₀(support); circle area scales with total ratings",
        transform=ax.transAxes,
        fontsize=11.5,
        color=MUTED,
        va="bottom",
    )
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.yaxis.grid(False)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    footer(fig, "Source: saved aggregate output from the Parfumo-derived branch; descriptive only.")
    fig.subplots_adjust(left=0.17, right=0.96, top=0.84, bottom=0.12)
    save(fig, "brand_rating_support.png")


def accord_shift_chart() -> None:
    frame = pd.read_csv(DATA / "accord_shift.csv").sort_values("share_change")
    frame["change_pp"] = frame["share_change"] * 100
    fig, ax = plt.subplots(figsize=(12.8, 7.6))
    colors = [LIGHT_BLUE] * len(frame)
    colors[-1] = ORANGE
    ax.barh(frame["accord"].str.title(), frame["change_pp"], color=colors, height=0.62)

    for position, value in enumerate(frame["change_pp"]):
        ax.text(value + 0.055, position, f"+{value:.2f} pp", va="center", fontsize=10.5)

    ax.axvline(0, color=NAVY, linewidth=1)
    ax.set_xlim(0, max(3.25, frame["change_pp"].max() * 1.18))
    ax.set_xlabel("Percentage-point change in share of accord observations")
    ax.set_title("Creamy and sweet accords gained the most share", loc="left", pad=28)
    ax.text(
        0,
        1.02,
        "2018–2024 compared with 2000–2017; minimum 80 observations in each period",
        transform=ax.transAxes,
        fontsize=11.5,
        color=MUTED,
        va="bottom",
    )
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.yaxis.grid(False)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    footer(fig, "Source: saved aggregate output from the Parfumo-derived branch; association, not causation.")
    fig.subplots_adjust(left=0.15, right=0.96, top=0.83, bottom=0.13)
    save(fig, "recent_accord_shift.png")


def accord_trend_chart() -> None:
    frame = pd.read_csv(DATA / "accord_trends.csv")
    selected = ["sweet", "floral", "spicy", "woody", "fresh", "creamy"]
    colors = [ORANGE, BLUE, PURPLE, TEAL, RED, GOLD]
    fig, ax = plt.subplots(figsize=(13.8, 8.0))

    for accord, color in zip(selected, colors):
        series = frame.loc[frame["accord"] == accord].sort_values("year")
        ax.plot(
            series["year"],
            series["share"],
            label=accord.title(),
            color=color,
            linewidth=2.8,
            marker="o",
            markersize=4.5,
        )

    ax.set_xlim(2010, 2024)
    ax.set_xticks(range(2010, 2025, 2))
    ax.set_ylim(0, 0.155)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Release year")
    ax.set_ylabel("Share of all accord observations in the year")
    ax.set_title("Accord composition shifted across 2010–2024 releases", loc="left", pad=28)
    ax.text(
        0,
        1.02,
        "Six selected series from the complete eight-accord aggregate table",
        transform=ax.transAxes,
        fontsize=11.5,
        color=MUTED,
        va="bottom",
    )
    ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.13))
    ax.grid(True, color=GRID, linewidth=0.8)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    footer(fig, "Source: saved aggregate output from the Parfumo-derived branch; shares are observational.")
    fig.subplots_adjust(left=0.10, right=0.97, top=0.84, bottom=0.22)
    save(fig, "accord_trends.png")


def note_lift_chart() -> None:
    frame = pd.read_csv(DATA / "note_lift_top10.csv").sort_values("lift")
    fig, ax = plt.subplots(figsize=(12.8, 7.6))
    left = 1.0
    colors = [LIGHT_BLUE] * len(frame)
    colors[-1] = ORANGE
    ax.barh(
        frame["note"].str.title(),
        frame["lift"] - left,
        left=left,
        color=colors,
        height=0.62,
    )
    for position, (_, row) in enumerate(frame.iterrows()):
        ax.text(
            row["lift"] + 0.045,
            position,
            f"{row['lift']:.2f}×  |  n={int(row['high_count'])}",
            va="center",
            fontsize=10.5,
        )

    ax.axvline(1.0, color=NAVY, linewidth=1.4)
    ax.set_xlim(1.0, max(3.85, frame["lift"].max() * 1.08))
    ax.set_xlabel("Lift relative to the note's rate in all cleaned fragrances")
    ax.set_title("Selected notes were overrepresented in the high-rated subset", loc="left", pad=28)
    ax.text(
        0,
        1.02,
        "High-rated = rating ≥ 8.0 with ≥ 25 ratings; labels show subset occurrence count",
        transform=ax.transAxes,
        fontsize=11.5,
        color=MUTED,
        va="bottom",
    )
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.yaxis.grid(False)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    footer(fig, "Source: saved aggregate output from the Parfumo-derived branch; association, not causation.")
    fig.subplots_adjust(left=0.15, right=0.96, top=0.83, bottom=0.13)
    save(fig, "high_rated_note_lift.png")


def main() -> None:
    configure()
    brand_chart()
    accord_shift_chart()
    accord_trend_chart()
    note_lift_chart()
    print("created 4 visuals")


if __name__ == "__main__":
    main()

