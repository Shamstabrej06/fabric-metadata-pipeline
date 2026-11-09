# Pipeline run report

Run date: 2026-11-08
Metadata version: 1.0
Load duration: 0.05 seconds

## Files processed

| File | Source | Rows read | Clean | Quarantined |
| --- | --- | ---: | ---: | ---: |
| store_a_day1.csv | store_a_pos | 40 | 35 | 5 |
| store_b_day1.csv | store_b_legacy | 40 | 35 | 5 |
| store_c_day1.csv | store_c_new | 40 | 38 | 2 |

## Schema drift detected

### store_a_day1.csv (store_a_pos)

- Columns mapped: 8 (OrderID, OrderDate, Store, Product, Category, Qty, Price, Email)
- Extra columns ignored: none
- Missing columns defaulted from metadata: none

### store_b_day1.csv (store_b_legacy)

- Columns mapped: 8 (Ord_No, Trans_Date, Location, Item_Name, Dept, Units, Unit_Price, Cust_Mail)
- Extra columns ignored: none
- Missing columns defaulted from metadata: none

### store_c_day1.csv (store_c_new)

- Columns mapped: 7 (TxnID, SaleDate, Outlet, Item, Qnty, Rate, MailID)
- Extra columns ignored: ItemGroup, Discount_Pct
- Missing columns defaulted from metadata: category = "Uncategorized"

## Totals

- Rows read: 120
- Clean rows loaded: 108
- Quarantined rows: 12
- Clean row rate: 90.0%

## Quarantine by rejection reason

| Rejection reason | Rows |
| --- | ---: |
| Duplicate order_id | 3 |
| Invalid quantity | 2 |
| Invalid unit_price | 2 |
| Invalid customer_email | 2 |
| Future order_date | 1 |
| Invalid order_date | 1 |
| Missing product_name | 1 |

## Outputs

- `outputs/clean_sales.csv` — the unified silver table (108 rows).
- `outputs/quarantine.csv` — rejected rows with their reason (12 rows).
- `outputs/run_report.md` — this report.
