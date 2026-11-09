"""Build the NorthMart sales dashboard workbook.

Reads the pipeline's clean output (``outputs/clean_sales.csv``) and builds
``outputs/Sales_Dashboard.xlsx`` with three sheets:

* ``Dashboard``    - KPI cells driven by real Excel formulas over the data
                     sheet, revenue-by-store and top-5-products tables, and
                     two native Excel charts.
* ``Clean_Data``   - the full clean table (108 rows), with filters on and
                     the header row frozen.
* ``Instructions`` - what the workbook is, where the data came from, and
                     how to refresh it after the next pipeline run.

Usage
-----
    python src/build_dashboard.py

Run ``src/pipeline.py`` first so ``outputs/clean_sales.csv`` exists.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

REPO_ROOT = Path(__file__).resolve().parent.parent
CLEAN_CSV = REPO_ROOT / "outputs" / "clean_sales.csv"
WORKBOOK_PATH = REPO_ROOT / "outputs" / "Sales_Dashboard.xlsx"

# ---------------------------------------------------------------------------
# Formatting palette (professional, print-friendly)
# ---------------------------------------------------------------------------
NAVY = "1F3864"
NAVY_FILL = PatternFill("solid", fgColor=NAVY)
LIGHT_GREY_FILL = PatternFill("solid", fgColor="D9E1F2")
WHITE_BOLD = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Calibri", size=16, bold=True, color=NAVY)
SUBTITLE_FONT = Font(name="Calibri", size=11, color="595959")
LABEL_FONT = Font(name="Calibri", size=11, bold=True)
BODY_FONT = Font(name="Calibri", size=11)
KPI_VALUE_FONT = Font(name="Calibri", size=14, bold=True, color=NAVY)
THIN_BORDER = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)
MONEY_FMT = '"$"#,##0.00'
PCT_FMT = "0.0%"
INT_FMT = "#,##0"

# The load totals come from the pipeline run that produced clean_sales.csv
# (see outputs/run_report.md). They are recorded here so the workbook can
# show the clean-row rate; the clean-row count itself is a live formula.
ROWS_READ = 120
QUARANTINED = 12


def style_header_row(ws, row: int, n_cols: int) -> None:
    """Apply the navy header style to every cell in one row."""
    for col in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = NAVY_FILL
        cell.font = WHITE_BOLD
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER


def build_clean_data_sheet(wb: Workbook, clean: pd.DataFrame) -> str:
    """Write the full clean table; return the data range used by formulas."""
    ws = wb.create_sheet("Clean_Data")
    columns = list(clean.columns)
    ws.append(columns)
    style_header_row(ws, 1, len(columns))
    for _, row in clean.iterrows():
        ws.append(list(row))
    last_row = len(clean) + 1

    # Numbers: quantities as integers, money with 2 decimals.
    for r in range(2, last_row + 1):
        ws.cell(row=r, column=6).number_format = INT_FMT          # quantity
        ws.cell(row=r, column=7).number_format = MONEY_FMT        # unit_price
        ws.cell(row=r, column=8).number_format = MONEY_FMT        # line_total
        for c in range(1, len(columns) + 1):
            ws.cell(row=r, column=c).font = BODY_FONT
            ws.cell(row=r, column=c).border = THIN_BORDER

    widths = {"A": 12, "B": 13, "C": 10, "D": 38, "E": 15,
              "F": 10, "G": 12, "H": 12, "I": 28}
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{last_row}"
    ws.freeze_panes = "A2"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return f"2:{last_row}"


def build_dashboard_sheet(
    wb: Workbook, clean: pd.DataFrame, data_rows: str
) -> None:
    """Build the Dashboard sheet: KPIs, tables and charts."""
    ws = wb.create_sheet("Dashboard", 0)
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    first, last = data_rows.split(":")
    data = f"Clean_Data!A{first}:I{last}"

    ws["A1"] = "NorthMart Retail Group — Sales Dashboard"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Clean sales loaded by the metadata-driven ingestion pipeline "
                "(silver.clean_sales). All figures below are live Excel "
                "formulas over the Clean_Data sheet.")
    ws["A2"].font = SUBTITLE_FONT
    ws.merge_cells("A2:H2")

    # ---- KPI block (row 4 header, row 5 values) ---------------------------
    ws["A4"] = "Key figures"
    ws["A4"].font = LABEL_FONT
    kpis = [
        ("Total Revenue", f"=SUM(Clean_Data!H{first}:H{last})", MONEY_FMT),
        ("Total Orders", f"=COUNTA(Clean_Data!A{first}:A{last})", INT_FMT),
        ("Average Order Value", "=B5/C5", MONEY_FMT),
        ("Clean Row %", "=C11/B11", PCT_FMT),
    ]
    for i, (label, formula, fmt) in enumerate(kpis):
        col = 2 + i  # columns B..E
        ws.cell(row=4, column=col, value=label).font = LABEL_FONT
        ws.cell(row=4, column=col).alignment = Alignment(horizontal="center")
        cell = ws.cell(row=5, column=col, value=formula)
        cell.font = KPI_VALUE_FONT
        cell.number_format = fmt
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER
    ws["A5"] = ""
    ws.column_dimensions["A"].width = 22
    for col in "BCDE":
        ws.column_dimensions[col].width = 20

    # ---- Load summary (rows 9-12) ------------------------------------------
    ws["A9"] = "Load summary (this run)"
    ws["A9"].font = LABEL_FONT
    summary = [
        ("Rows read", ROWS_READ, INT_FMT),
        ("Clean rows loaded", f"=COUNTA(Clean_Data!A{first}:A{last})", INT_FMT),
        ("Quarantined rows", QUARANTINED, INT_FMT),
    ]
    for i, (label, value, fmt) in enumerate(summary):
        r = 10 + i
        ws.cell(row=r, column=1, value=label).font = BODY_FONT
        cell = ws.cell(row=r, column=2, value=value)
        cell.font = BODY_FONT
        cell.number_format = fmt
        cell.alignment = Alignment(horizontal="right")
    # Clean Row % (row 5) reads C11/B11: clean rows / rows read.
    ws["A12"] = "Clean row rate is Total Orders ÷ Rows read; see KPI above."

    # ---- Revenue by store (rows 14-19) --------------------------------------
    ws["A14"] = "Revenue by store"
    ws["A14"].font = LABEL_FONT
    ws["A15"] = "Store"
    ws["B15"] = "Orders"
    ws["C15"] = "Revenue"
    style_header_row(ws, 15, 3)
    for i, store in enumerate(["A", "B", "C"]):
        r = 16 + i
        ws.cell(row=r, column=1, value=f"Store {store}").font = BODY_FONT
        ws.cell(row=r, column=2,
               value=f'=COUNTIF(Clean_Data!$C${first}:$C${last},"={store}")'
               ).number_format = INT_FMT
        ws.cell(row=r, column=3,
               value=f'=SUMIF(Clean_Data!$C${first}:$C${last},"={store}",'
                     f'Clean_Data!$H${first}:$H${last})'
               ).number_format = MONEY_FMT
        for c in range(1, 4):
            ws.cell(row=r, column=c).border = THIN_BORDER
    total_row = 19
    ws.cell(row=total_row, column=1, value="Total").font = LABEL_FONT
    ws.cell(row=total_row, column=2, value="=SUM(B16:B18)").font = LABEL_FONT
    ws.cell(row=total_row, column=2).number_format = INT_FMT
    ws.cell(row=total_row, column=3, value="=SUM(C16:C18)").font = LABEL_FONT
    ws.cell(row=total_row, column=3).number_format = MONEY_FMT

    store_chart = BarChart()
    store_chart.type = "col"
    store_chart.title = "Revenue by store"
    store_chart.y_axis.title = "Revenue ($)"
    store_chart.x_axis.title = "Store"
    store_chart.style = 10
    store_chart.height = 7.5
    store_chart.width = 14
    store_chart.shape = 4
    store_chart.legend = None
    chart_data = Reference(ws, min_col=3, min_row=15, max_row=18)
    cats = Reference(ws, min_col=1, min_row=16, max_row=18)
    store_chart.add_data(chart_data, titles_from_data=True)
    store_chart.set_categories(cats)
    store_chart.dataLabels = None
    ws.add_chart(store_chart, "E14")

    # ---- Revenue by category (rows 21-28) -----------------------------------
    ws["A21"] = "Revenue by category"
    ws["A21"].font = LABEL_FONT
    ws["A22"] = "Category"
    ws["B22"] = "Orders"
    ws["C22"] = "Revenue"
    style_header_row(ws, 22, 3)
    categories = sorted(clean["category"].unique())
    for i, cat in enumerate(categories):
        r = 23 + i
        ws.cell(row=r, column=1, value=cat).font = BODY_FONT
        ws.cell(row=r, column=2,
               value=f'=COUNTIF(Clean_Data!$E${first}:$E${last},"={cat}")'
               ).number_format = INT_FMT
        ws.cell(row=r, column=3,
               value=f'=SUMIF(Clean_Data!$E${first}:$E${last},"={cat}",'
                     f'Clean_Data!$H${first}:$H${last})'
               ).number_format = MONEY_FMT
        for c in range(1, 4):
            ws.cell(row=r, column=c).border = THIN_BORDER
    cat_total = 23 + len(categories)
    ws.cell(row=cat_total, column=1, value="Total").font = LABEL_FONT
    ws.cell(row=cat_total, column=2,
           value=f"=SUM(B23:B{cat_total - 1})").font = LABEL_FONT
    ws.cell(row=cat_total, column=2).number_format = INT_FMT
    ws.cell(row=cat_total, column=3,
           value=f"=SUM(C23:C{cat_total - 1})").font = LABEL_FONT
    ws.cell(row=cat_total, column=3).number_format = MONEY_FMT

    cat_chart = BarChart()
    cat_chart.type = "col"
    cat_chart.title = "Revenue by category"
    cat_chart.y_axis.title = "Revenue ($)"
    cat_chart.x_axis.title = "Category"
    cat_chart.style = 10
    cat_chart.height = 7.5
    cat_chart.width = 16
    cat_chart.shape = 4
    cat_chart.legend = None
    chart_data = Reference(ws, min_col=3, min_row=22,
                           max_row=22 + len(categories))
    cats = Reference(ws, min_col=1, min_row=23, max_row=22 + len(categories))
    cat_chart.add_data(chart_data, titles_from_data=True)
    cat_chart.set_categories(cats)
    ws.add_chart(cat_chart, "E21")

    # ---- Top 5 products by revenue (rows 31-37) -----------------------------
    top5 = (clean.groupby("product_name")["line_total"].sum()
            .sort_values(ascending=False).head(5))
    ws["A31"] = "Top 5 products by revenue"
    ws["A31"].font = LABEL_FONT
    ws["A32"] = "Product"
    ws["B32"] = "Revenue"
    style_header_row(ws, 32, 2)
    for i, (product, revenue) in enumerate(top5.items()):
        r = 33 + i
        ws.cell(row=r, column=1, value=product).font = BODY_FONT
        cell = ws.cell(row=r, column=2, value=float(revenue))
        cell.font = BODY_FONT
        cell.number_format = MONEY_FMT
        for c in range(1, 3):
            ws.cell(row=r, column=c).border = THIN_BORDER
    ws["A38"] = ("Top 5 is a snapshot computed from Clean_Data at build time; "
                 "refresh it by re-running this script after the next "
                 "pipeline run.")
    ws["A38"].font = SUBTITLE_FONT
    ws.merge_cells("A38:H38")


def build_instructions_sheet(wb: Workbook) -> None:
    """Explain the workbook: what it is, where the data came from, refresh."""
    ws = wb.create_sheet("Instructions")
    ws.column_dimensions["A"].width = 110
    lines = [
        ("NorthMart Sales Dashboard — Instructions", TITLE_FONT),
        ("", BODY_FONT),
        ("What this workbook is", LABEL_FONT),
        ("This workbook is the reporting layer of the Metadata-Driven "
         "Lakehouse Ingestion Pipeline portfolio project. The Dashboard sheet "
         "summarises the clean sales table; the Clean_Data sheet holds every "
         "clean row.", BODY_FONT),
        ("", BODY_FONT),
        ("Where the data came from", LABEL_FONT),
        ("One daily sales CSV from each of three fictional NorthMart store "
         "systems. The pipeline (src/pipeline.py) mapped each file's columns "
         "to one unified schema using config/metadata.json, detected schema "
         "drift, validated every row, and loaded 108 clean rows into "
         "outputs/clean_sales.csv. 12 rows failed validation and were "
         "quarantined with a rejection reason (see outputs/quarantine.csv) — "
         "they are not in this workbook.", BODY_FONT),
        ("", BODY_FONT),
        ("How to refresh it", LABEL_FONT),
        ("1. Drop the new daily CSV files into data/raw/.", BODY_FONT),
        ("2. Run:  python src/pipeline.py", BODY_FONT),
        ("3. Run:  python src/build_dashboard.py", BODY_FONT),
        ("4. Re-open Sales_Dashboard.xlsx. The KPI cells, store and category "
         "tables and both charts update from the new Clean_Data sheet; the "
         "Top 5 table is rebuilt by the script.", BODY_FONT),
        ("", BODY_FONT),
        ("Notes", LABEL_FONT),
        ("- Figures are live Excel formulas over Clean_Data, except the "
         "Top 5 table, which is a snapshot rebuilt by this script.", BODY_FONT),
        ("- All amounts are in Canadian dollars (CAD).", BODY_FONT),
        ("- Store C has no category in its source file, so its rows are "
         "categorised as \"Uncategorized\" by the metadata default.", BODY_FONT),
    ]
    for i, (text, font) in enumerate(lines, start=1):
        cell = ws.cell(row=i, column=1, value=text)
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if text.startswith("1. ") or text.startswith("2. ") \
                or text.startswith("3. ") or text.startswith("4. "):
            cell.alignment = Alignment(indent=1, wrap_text=True)
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def main() -> None:
    """Read clean_sales.csv and write Sales_Dashboard.xlsx."""
    if not CLEAN_CSV.exists():
        raise SystemExit(
            f"Clean data not found: {CLEAN_CSV}\n"
            "Run the pipeline first:  python src/pipeline.py"
        )
    clean = pd.read_csv(CLEAN_CSV)
    wb = Workbook()
    wb.remove(wb.active)  # drop the default blank sheet
    data_rows = build_clean_data_sheet(wb, clean)
    build_dashboard_sheet(wb, clean, data_rows)
    build_instructions_sheet(wb)
    wb.active = wb["Dashboard"]
    wb.save(WORKBOOK_PATH)
    print(f"Dashboard written to {WORKBOOK_PATH}")
    print(f"  {len(clean)} clean rows on the Clean_Data sheet")


if __name__ == "__main__":
    main()
