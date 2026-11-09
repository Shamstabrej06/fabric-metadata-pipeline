"""Generate the three portfolio images for the project.

Produces, in ``assets/``:

* ``architecture.png`` - flow diagram of the metadata-driven pipeline.
* ``results.png``      - the actual run statistics as clean visuals.
* ``dashboard.png``    - revenue by store and revenue by category.

All figures come from the pipeline run recorded in
``outputs/run_report.md`` (120 rows read, 108 clean, 12 quarantined;
total revenue $28,855.69). If the sample data ever changes, re-run
``src/pipeline.py`` first and update the constants below to match the
new run report.

Usage
-----
    python src/make_assets.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

matplotlib.use("Agg")

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "assets"

# ---------------------------------------------------------------------------
# Run figures (from outputs/run_report.md - keep in sync with the run)
# ---------------------------------------------------------------------------
ROWS_READ = 120
ROWS_CLEAN = 108
ROWS_QUARANTINED = 12

REASONS = [
    ("Duplicate order_id", 3),
    ("Invalid quantity", 2),
    ("Invalid unit_price", 2),
    ("Invalid customer_email", 2),
    ("Future order_date", 1),
    ("Invalid order_date", 1),
    ("Missing product_name", 1),
]

REVENUE_BY_STORE = [("Store A", 4295.65), ("Store B", 9380.63),
                    ("Store C", 15179.41)]
REVENUE_BY_CATEGORY = [
    ("Uncategorized", 15179.41),
    ("Electronics", 8081.74),
    ("Clothing", 2279.60),
    ("Home", 1578.67),
    ("Personal Care", 982.61),
    ("Grocery", 753.66),
]

# ---------------------------------------------------------------------------
# Shared style: light background, dark text, clean professional look
# ---------------------------------------------------------------------------
NAVY = "#1F3864"
BLUE = "#2E75B6"
LIGHT_BLUE = "#D9E1F2"
GREEN = "#548235"
RED = "#C00000"
GREY = "#595959"

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#BFBFBF",
    "axes.labelcolor": "#262626",
    "text.color": "#262626",
    "xtick.color": "#404040",
    "ytick.color": "#404040",
    "font.family": "DejaVu Sans",
})


def _box(ax, x, y, w, h, title, lines, fill=LIGHT_BLUE, title_color=NAVY,
         body_color="#262626"):
    """Draw one labelled box and return its centre-right / centre-left points."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.06,rounding_size=0.12",
        facecolor=fill, edgecolor=NAVY, linewidth=1.4,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h - 0.32, title, ha="center", va="top",
            fontsize=10, fontweight="bold", color=title_color)
    ax.text(x + w / 2, y + h - 0.75, "\n".join(lines), ha="center", va="top",
            fontsize=8.5, color=body_color)
    return (x + w, y + h / 2), (x, y + h / 2)


def _arrow(ax, start, end):
    """Draw a straight arrow between two points."""
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=14,
        color=NAVY, linewidth=1.4, shrinkA=2, shrinkB=2,
    ))


def make_architecture() -> None:
    """Flow diagram: 3 store CSVs -> metadata -> pipeline -> outputs."""
    fig, ax = plt.subplots(figsize=(13, 6.2))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 6.2)
    ax.axis("off")
    ax.set_title("Metadata-Driven Lakehouse Ingestion Pipeline — Architecture",
                 fontsize=14, fontweight="bold", color=NAVY, pad=14)

    # Column 1: the three source files.
    sources = [
        ("Store A — POS System", ["store_a_day1.csv", "8 columns, ISO dates"]),
        ("Store B — Legacy Export", ["store_b_day1.csv", "DD/MM/YYYY, $ prices"]),
        ("Store C — New System", ["store_c_day1.csv", "renamed cols, extra col,",
                                  "no category column"]),
    ]
    source_rights = []
    for i, (title, lines) in enumerate(sources):
        y = 4.6 - i * 1.65
        right, _ = _box(ax, 0.2, y, 2.5, 1.35, title, lines)
        source_rights.append((right[0], right[1]))

    # Column 2: the metadata config.
    meta_right, meta_left = _box(
        ax, 3.5, 2.35, 2.4, 1.9, "Metadata Config",
        ["metadata.json", "column mappings", "date formats",
         "defaults", "validation rules"],
        fill="#FFF2CC",
    )
    for sx, sy in source_rights:
        _arrow(ax, (sx, sy), (meta_left[0], meta_left[1]))

    # Column 3: the ingestion pipeline.
    pipe_right, pipe_left = _box(
        ax, 6.7, 2.35, 2.4, 1.9, "Ingestion Pipeline",
        ["1  Drift detection", "2  Column mapping", "3  Validation",
         "Python + pandas"],
        fill=NAVY, title_color="white", body_color="white",
    )
    _arrow(ax, meta_right, pipe_left)

    # Column 4: the two outputs.
    clean_right, clean_left = _box(
        ax, 9.9, 4.15, 2.6, 1.35, "Clean Table — silver",
        ["clean_sales.csv", "108 rows, one schema"],
        fill="#E2EFDA",
    )
    quar_right, quar_left = _box(
        ax, 9.9, 1.35, 2.6, 1.35, "Quarantine",
        ["quarantine.csv", "12 rows + rejection reason"],
        fill="#FCE4E4",
    )
    _arrow(ax, pipe_right, (clean_left[0], clean_left[1]))
    _arrow(ax, pipe_right, (quar_left[0], quar_left[1]))

    # The clean table feeds the Excel dashboard (noted under the outputs).
    ax.text(11.2, 0.55, "Clean rows feed the\nExcel dashboard",
            ha="center", va="top", fontsize=8.5, color=GREY, style="italic")
    ax.text(11.2, 3.35, "↓  Excel dashboard\n   (Sales_Dashboard.xlsx)",
            ha="center", va="top", fontsize=8.5, color=NAVY)
    fig.tight_layout()
    fig.savefig(ASSETS_DIR / "architecture.png", dpi=150,
                bbox_inches="tight")
    plt.close(fig)
    print("Wrote assets/architecture.png")


def make_results() -> None:
    """Run statistics: rows in/out and quarantine reasons."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    fig.suptitle("Pipeline run — 120 rows in, 108 clean, 12 quarantined (90.0% clean)",
                 fontsize=13, fontweight="bold", color=NAVY)

    # Left: rows read vs clean vs quarantined.
    ax = axes[0]
    labels = ["Rows read", "Clean", "Quarantined"]
    values = [ROWS_READ, ROWS_CLEAN, ROWS_QUARANTINED]
    colors = [BLUE, GREEN, RED]
    bars = ax.bar(labels, values, color=colors, width=0.6)
    ax.set_ylabel("Rows")
    ax.set_title("Rows processed", fontsize=11, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(0, 135)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 3, str(value),
                ha="center", fontsize=11, fontweight="bold")

    # Right: quarantine reasons (horizontal bar).
    ax = axes[1]
    names = [name for name, _ in REASONS]
    counts = [count for _, count in REASONS]
    bars = ax.barh(names[::-1], counts[::-1], color=RED, height=0.6)
    ax.set_xlabel("Rows quarantined")
    ax.set_title("Quarantine reasons", fontsize=11, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, 3.6)
    for bar, value in zip(bars, counts[::-1]):
        ax.text(value + 0.08, bar.get_y() + bar.get_height() / 2, str(value),
                va="center", fontsize=10, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(ASSETS_DIR / "results.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Wrote assets/results.png")


def make_dashboard() -> None:
    """Revenue by store and revenue by category."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    fig.suptitle("Clean sales revenue — $28,855.69 across 108 orders",
                 fontsize=13, fontweight="bold", color=NAVY)

    # Left: revenue by store.
    ax = axes[0]
    stores = [name for name, _ in REVENUE_BY_STORE]
    store_values = [value for _, value in REVENUE_BY_STORE]
    bars = ax.bar(stores, store_values, color=[BLUE, NAVY, GREEN], width=0.6)
    ax.set_ylabel("Revenue ($)")
    ax.set_title("Revenue by store", fontsize=11, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(0, 17000)
    for bar, value in zip(bars, store_values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 400,
                f"${value:,.2f}", ha="center", fontsize=10, fontweight="bold")

    # Right: revenue by category (horizontal, longest first).
    ax = axes[1]
    cats = [name for name, _ in REVENUE_BY_CATEGORY]
    cat_values = [value for _, value in REVENUE_BY_CATEGORY]
    bars = ax.barh(cats[::-1], cat_values[::-1], color=NAVY, height=0.6)
    ax.set_xlabel("Revenue ($)")
    ax.set_title("Revenue by category", fontsize=11, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, 17000)
    for bar, value in zip(bars, cat_values[::-1]):
        ax.text(value + 300, bar.get_y() + bar.get_height() / 2,
                f"${value:,.2f}", va="center", fontsize=9, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(ASSETS_DIR / "dashboard.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Wrote assets/dashboard.png")


def main() -> None:
    """Generate all three PNGs."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    make_architecture()
    make_results()
    make_dashboard()


if __name__ == "__main__":
    main()
