"""Metadata-driven lakehouse ingestion pipeline (reference implementation).

Story
-----
NorthMart Retail Group receives one daily sales CSV from each of its three
store systems. Every system exports a different schema, and the schemas drift
over time: renamed columns, extra columns, missing columns, different date
formats, and currency symbols in prices. Instead of hand-writing a pipeline
per file, ONE metadata configuration (``config/metadata.json``) drives the
whole load:

* source-to-target column mappings and target data types,
* the date format used by each source,
* defaults for columns a source does not send at all,
* the validation rules every row must pass.

The pipeline detects schema drift in each file, applies the metadata,
validates every row, loads clean rows into one unified target table
(``silver.clean_sales``) and quarantines bad rows with a specific rejection
reason (``silver.quarantine``).

Design note
-----------
This is the portable reference implementation: plain Python + pandas, so
anyone can run it locally with no cloud account. It mirrors how the same
pattern is built on Microsoft Fabric — the metadata becomes a Lakehouse
table, the mapping/validation steps become PySpark notebook cells, and the
run becomes a Fabric pipeline activity. See ``README.md`` for that mapping.

Usage
-----
    python src/pipeline.py

Inputs:  ``config/metadata.json`` and the CSV files in ``data/raw/``.
Outputs: ``outputs/clean_sales.csv``, ``outputs/quarantine.csv`` and
         ``outputs/run_report.md``, plus a console summary.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths (all relative to the repository root, which is the parent of src/)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "metadata.json"
RAW_DIR = REPO_ROOT / "data" / "raw"
OUTPUT_DIR = REPO_ROOT / "outputs"

TARGET_COLUMNS = [
    "order_id",
    "order_date",
    "store_id",
    "product_name",
    "category",
    "quantity",
    "unit_price",
    "line_total",
    "customer_email",
]

# A basic email pattern: something@domain.tld. Good enough to catch typos
# (missing @, double @@, missing domain) without rejecting real addresses.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Step 1 - Load the metadata configuration
# ---------------------------------------------------------------------------
def load_metadata(config_path: Path) -> dict:
    """Read and return the metadata configuration as a dict."""
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Step 2 - Discover the raw files listed in the metadata
# ---------------------------------------------------------------------------
def discover_files(metadata: dict) -> list[tuple[dict, Path]]:
    """Return [(source_config, file_path)] for every source in the metadata.

    Files are returned in the order the sources appear in the config, which
    is also the order used for the cross-file duplicate order_id check.
    """
    found = []
    for source in metadata["sources"]:
        path = RAW_DIR / source["file_pattern"]
        if not path.exists():
            print(f"  WARNING: {source['source_name']}: file not found: {path}")
            continue
        found.append((source, path))
    return found


# ---------------------------------------------------------------------------
# Step 3 - Schema drift detection
# ---------------------------------------------------------------------------
def detect_drift(file_columns: list[str], source: dict) -> dict:
    """Compare a file's actual columns with the metadata mapping.

    Returns a drift report with three lists:
      * ``mapped``   - source columns that map onto a target column
                       (a rename is simply a mapping entry, e.g. Ord_No
                       -> order_id).
      * ``extra``    - columns present in the file but not in the mapping.
                       They are ignored by the load.
      * ``missing``  - target columns with no source column. They are
                       filled from ``defaults`` in the metadata; a target
                       column that is missing AND has no default is an
                       error for every row.
    """
    mapping = source["column_mapping"]
    mapped = [c for c in file_columns if c in mapping]
    extra = [c for c in file_columns if c not in mapping]
    mapped_targets = {mapping[c]["target"] for c in mapped}
    missing = [
        col["name"]
        for col in _target_columns(source)
        if col["name"] not in mapped_targets and col["name"] != "line_total"
    ]
    return {"mapped": mapped, "extra": extra, "missing": missing}


def _target_columns(source: dict) -> list[dict]:
    """Target columns for a source (kept in one place for reuse)."""
    # The metadata carries the full target schema at the top level; the
    # pipeline reads it from the loaded config via a module-level cache.
    return _TARGET_SCHEMA


_TARGET_SCHEMA: list[dict] = []


# ---------------------------------------------------------------------------
# Step 4 - Read one raw file and apply the metadata mapping
# ---------------------------------------------------------------------------
def read_and_map(source: dict, path: Path) -> pd.DataFrame:
    """Read a raw CSV as text and rename its columns to the target schema.

    Everything is read as a string first so that values like "$1,249.99" or
    "N/A" survive intact until the coercion step, where they are cleaned or
    rejected with a reason instead of crashing the load.
    """
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    mapping = {
        src_col: spec["target"]
        for src_col, spec in source["column_mapping"].items()
    }
    mapped = raw.rename(columns=mapping)
    # Keep only the columns the metadata knows about; extras are dropped
    # here (they were already reported as drift in detect_drift).
    keep = [c for c in mapped.columns if c in mapping.values()]
    mapped = mapped[keep].copy()
    # Fill in columns the source does not send, from the metadata defaults.
    for target_col, default_value in source.get("defaults", {}).items():
        if target_col not in mapped.columns:
            mapped[target_col] = default_value
    # Guarantee every target column exists (empty string where unknown).
    for col in TARGET_COLUMNS:
        if col not in mapped.columns and col != "line_total":
            mapped[col] = ""
    # Normalise whitespace.
    for col in mapped.columns:
        mapped[col] = mapped[col].astype(str).str.strip()
    return mapped


# ---------------------------------------------------------------------------
# Step 5 - Type coercion
# ---------------------------------------------------------------------------
def coerce_types(df: pd.DataFrame, source: dict) -> pd.DataFrame:
    """Coerce the mapped frame to the target types, recording failures.

    Coercion never drops a row. A value that cannot be coerced becomes a
    missing value (``NaT``/``NaN``/``None``) and the validation step then
    rejects the row with a specific reason.
    """
    df = df.copy()
    date_format = source["date_format"]

    def parse_date(value: str):
        if not value:
            return pd.NaT
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            return pd.NaT

    df["order_date"] = df["order_date"].apply(parse_date)

    def parse_quantity(value: str):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    df["quantity"] = df["quantity"].apply(parse_quantity)

    def parse_price(value: str):
        """Strip currency symbols and thousand separators, then parse."""
        if not value:
            return None
        cleaned = value.replace("$", "").replace(",", "").strip()
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None

    df["unit_price"] = df["unit_price"].apply(parse_price)
    return df


# ---------------------------------------------------------------------------
# Step 6 - Validation
# ---------------------------------------------------------------------------
def validate_rows(
    df: pd.DataFrame, seen_order_ids: set[str], run_date: date
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a coerced frame into clean and quarantined rows.

    Every rule in ``config/metadata.json`` is enforced here. A row can fail
    more than one rule; all of its reasons are recorded, joined with "; ".
    ``seen_order_ids`` is shared across files so order_id uniqueness is
    checked across the whole load, not just within one file.
    """
    clean_rows: list[dict] = []
    quarantined_rows: list[dict] = []

    for _, row in df.iterrows():
        reasons: list[str] = []
        order_id = row["order_id"]

        # Rule: order_id_present + order_id_unique
        if not order_id:
            reasons.append("Missing order_id")
        elif order_id in seen_order_ids:
            reasons.append("Duplicate order_id")
        else:
            seen_order_ids.add(order_id)

        # Rule: order_date_valid + order_date_not_future
        order_date = row["order_date"]
        if order_date is pd.NaT or order_date is None or pd.isna(order_date):
            reasons.append("Invalid order_date")
        elif order_date > run_date:
            reasons.append("Future order_date")

        # Rule: quantity_range (1-999)
        quantity = row["quantity"]
        if quantity is None or pd.isna(quantity) or not 1 <= int(quantity) <= 999:
            reasons.append("Invalid quantity")

        # Rule: unit_price_positive
        unit_price = row["unit_price"]
        if unit_price is None or pd.isna(unit_price) or unit_price <= 0:
            reasons.append("Invalid unit_price")

        # Rule: product_name_present + category_present
        if not row["product_name"]:
            reasons.append("Missing product_name")
        if not row["category"]:
            reasons.append("Missing category")

        # Rule: customer_email_format (only when an email is present)
        email = row["customer_email"]
        if email and not EMAIL_PATTERN.match(email):
            reasons.append("Invalid customer_email")

        record = {col: row[col] for col in TARGET_COLUMNS if col != "line_total"}
        if reasons:
            record["source_file"] = row["_source_file"]
            record["rejection_reason"] = "; ".join(reasons)
            quarantined_rows.append(record)
        else:
            # Derived column: line_total = quantity x unit_price.
            line_total = (row["unit_price"] * int(row["quantity"])).quantize(
                Decimal("0.01")
            )
            record["line_total"] = line_total
            clean_rows.append(record)

    clean_df = pd.DataFrame(clean_rows, columns=TARGET_COLUMNS)
    quarantine_cols = [c for c in TARGET_COLUMNS if c != "line_total"] + [
        "source_file",
        "rejection_reason",
    ]
    quarantine_df = pd.DataFrame(quarantined_rows, columns=quarantine_cols)
    return clean_df, quarantine_df


# ---------------------------------------------------------------------------
# Step 7 - Run report (Markdown)
# ---------------------------------------------------------------------------
def build_run_report(
    metadata: dict,
    per_file: list[dict],
    total_read: int,
    total_clean: int,
    total_quarantined: int,
    reason_counts: dict[str, int],
    duration_seconds: float,
    run_date: date,
) -> str:
    """Render the Markdown run report written to outputs/run_report.md."""
    lines = [
        "# Pipeline run report",
        "",
        f"Run date: {run_date.isoformat()}",
        f"Metadata version: {metadata.get('version', 'n/a')}",
        f"Load duration: {duration_seconds:.2f} seconds",
        "",
        "## Files processed",
        "",
        "| File | Source | Rows read | Clean | Quarantined |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for entry in per_file:
        lines.append(
            f"| {entry['file']} | {entry['source']} | {entry['read']} | "
            f"{entry['clean']} | {entry['quarantined']} |"
        )
    lines += [
        "",
        "## Schema drift detected",
        "",
    ]
    for entry in per_file:
        drift = entry["drift"]
        lines.append(f"### {entry['file']} ({entry['source']})")
        lines.append("")
        lines.append(f"- Columns mapped: {len(drift['mapped'])} "
                     f"({', '.join(drift['mapped'])})")
        if drift["extra"]:
            lines.append(f"- Extra columns ignored: {', '.join(drift['extra'])}")
        else:
            lines.append("- Extra columns ignored: none")
        if drift["missing"]:
            lines.append(
                "- Missing columns defaulted from metadata: "
                + ", ".join(
                    f"{col} = \"{entry['defaults'].get(col, '')}\""
                    for col in drift["missing"]
                )
            )
        else:
            lines.append("- Missing columns defaulted from metadata: none")
        lines.append("")
    lines += [
        "## Totals",
        "",
        f"- Rows read: {total_read}",
        f"- Clean rows loaded: {total_clean}",
        f"- Quarantined rows: {total_quarantined}",
        f"- Clean row rate: {100 * total_clean / total_read:.1f}%",
        "",
        "## Quarantine by rejection reason",
        "",
        "| Rejection reason | Rows |",
        "| --- | ---: |",
    ]
    for reason, count in sorted(reason_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {reason} | {count} |")
    lines += [
        "",
        "## Outputs",
        "",
        "- `outputs/clean_sales.csv` — the unified silver table "
        f"({total_clean} rows).",
        "- `outputs/quarantine.csv` — rejected rows with their reason "
        f"({total_quarantined} rows).",
        "- `outputs/run_report.md` — this report.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------
def main() -> None:
    """Run the full load: discover, drift-check, map, coerce, validate, write."""
    global _TARGET_SCHEMA
    started = time.time()
    run_date = date.today()
    print("Metadata-Driven Lakehouse Ingestion Pipeline")
    print("=" * 52)

    metadata = load_metadata(CONFIG_PATH)
    _TARGET_SCHEMA = metadata["target_columns"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = discover_files(metadata)
    print(f"Metadata version {metadata.get('version', 'n/a')}: "
          f"{len(files)} source file(s) found.\n")

    seen_order_ids: set[str] = set()
    all_clean: list[pd.DataFrame] = []
    all_quarantined: list[pd.DataFrame] = []
    per_file: list[dict] = []
    total_read = 0

    for source, path in files:
        raw = pd.read_csv(path, dtype=str, keep_default_na=False)
        drift = detect_drift(list(raw.columns), source)
        mapped = read_and_map(source, path)
        mapped["_source_file"] = path.name
        coerced = coerce_types(mapped, source)
        clean_df, quarantine_df = validate_rows(coerced, seen_order_ids, run_date)

        total_read += len(raw)
        per_file.append({
            "file": path.name,
            "source": source["source_name"],
            "read": len(raw),
            "clean": len(clean_df),
            "quarantined": len(quarantine_df),
            "drift": drift,
            "defaults": source.get("defaults", {}),
        })
        all_clean.append(clean_df)
        all_quarantined.append(quarantine_df)

        print(f"{path.name} ({source['source_name']})")
        print(f"  Drift: {len(drift['mapped'])} columns mapped, "
              f"{len(drift['extra'])} extra ignored "
              f"({', '.join(drift['extra']) or 'none'}), "
              f"{len(drift['missing'])} missing defaulted "
              f"({', '.join(drift['missing']) or 'none'})")
        print(f"  Rows: {len(raw)} read, {len(clean_df)} clean, "
              f"{len(quarantine_df)} quarantined\n")

    clean = (
        pd.concat(all_clean, ignore_index=True)
        if all_clean else pd.DataFrame(columns=TARGET_COLUMNS)
    )
    quarantine = (
        pd.concat(all_quarantined, ignore_index=True)
        if all_quarantined
        else pd.DataFrame(columns=[c for c in TARGET_COLUMNS if c != "line_total"]
                          + ["source_file", "rejection_reason"])
    )

    # Normalise output types: dates as ISO strings, money with 2 decimals.
    clean_out = clean.copy()
    clean_out["order_date"] = pd.to_datetime(clean_out["order_date"]).dt.date.astype(str)
    clean_out["unit_price"] = clean_out["unit_price"].apply(lambda v: f"{v:.2f}")
    clean_out["line_total"] = clean_out["line_total"].apply(lambda v: f"{v:.2f}")
    clean_out.to_csv(OUTPUT_DIR / "clean_sales.csv", index=False)

    quarantine_out = quarantine.copy()
    quarantine_out["order_date"] = quarantine_out["order_date"].apply(
        lambda v: "" if pd.isna(v) else (v.isoformat() if hasattr(v, "isoformat") else str(v))
    )
    quarantine_out["unit_price"] = quarantine_out["unit_price"].apply(
        lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{v:.2f}"
    )
    quarantine_out.to_csv(OUTPUT_DIR / "quarantine.csv", index=False)

    # Quarantine counts by reason (a row with several reasons counts once
    # under each of its reasons).
    reason_counts: dict[str, int] = {}
    for reasons in quarantine["rejection_reason"]:
        for reason in str(reasons).split("; "):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    duration = time.time() - started
    report = build_run_report(
        metadata, per_file, total_read, len(clean), len(quarantine),
        reason_counts, duration, run_date,
    )
    (OUTPUT_DIR / "run_report.md").write_text(report, encoding="utf-8")

    print("=" * 52)
    print(f"TOTAL: {total_read} rows read, {len(clean)} clean, "
          f"{len(quarantine)} quarantined "
          f"({100 * len(clean) / total_read:.1f}% clean)")
    print(f"Outputs written to {OUTPUT_DIR}/")
    print("  - clean_sales.csv")
    print("  - quarantine.csv")
    print("  - run_report.md")


if __name__ == "__main__":
    main()
