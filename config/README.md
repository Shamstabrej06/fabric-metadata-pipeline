# Metadata configuration — plain-English guide

`metadata.json` is the heart of this project. It is the **single place** that
describes every store feed, so the pipeline code never needs to change when a
new store is added or a column is renamed. A business user can read this file
and understand exactly what the pipeline will do.

## Top-level keys

| Key | What it means |
| --- | --- |
| `version` | Version of this configuration file. Bump it when you change mappings or rules. |
| `project` | Name of the project this config belongs to. |
| `description` | One-paragraph summary of what the config does. |
| `target_table` | Name of the unified "silver" table clean rows are loaded into (`silver.clean_sales`). |
| `quarantine_table` | Name of the table bad rows go to (`silver.quarantine`), with the reason they were rejected. |
| `target_columns` | The unified schema every file is mapped into: column name, type, and whether it may be empty (`nullable`). |
| `sources` | One entry per store feed. This is the list the pipeline loops over. |
| `validation_rules` | The data-quality rules applied to every row, in plain English. |
| `derived_columns` | Columns the pipeline calculates itself — here, `line_total`. |

## One `sources` entry, key by key

| Key | What it means |
| --- | --- |
| `source_name` | Short id for the feed, e.g. `store_a_pos`. Used in logs and the drift report. |
| `description` | What this feed is, in plain words. |
| `file_pattern` | The file name (or pattern) to pick up from `data/raw/`. |
| `date_format` | How dates look in this file, written as a Python date code: `%Y-%m-%d` means `2026-01-19`, `%d/%m/%Y` means `29/01/2026`, `%b %d, %Y` means `Jan 11, 2026`. |
| `date_format_description` | The same thing in words, with an example. |
| `column_mapping` | The translation table: each source column name points at a target column and its type. A column that is **not** listed here is treated as an extra column and ignored (and reported as drift). |
| `defaults` | Values to fill in when a target column has no source column at all. Store C has no category column, so every Store C row gets `category = "Uncategorized"` from here. |

## `validation_rules`, key by key

| Key | What it means |
| --- | --- |
| `rule_id` | Short id for the rule, e.g. `quantity_range`. Used in code and reports. |
| `target_column` | Which unified column the rule checks. |
| `description` | The rule in plain English. |
| `severity` | Always `reject` in this project: a row that fails any rule goes to quarantine, never to the clean table. |
| `min` / `max` | Only on `quantity_range`: the allowed range is 1–999. |

## How to add a new store

1. Copy one `sources` entry and change `source_name`, `file_pattern`,
   `date_format`, and `column_mapping` to match the new file.
2. If the new file is missing a target column, add it to `defaults`.
3. Drop the new CSV into `data/raw/` and run the pipeline. No code changes.

## How to change a rule

Edit the `description` (and `min`/`max` where present) in
`validation_rules`. The pipeline reads the rules from this file, so the change
takes effect on the next run.
