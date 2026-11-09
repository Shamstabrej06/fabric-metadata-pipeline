# Upwork portfolio item + proposal copy

## Portfolio item

**Title:** Metadata-Driven Lakehouse Ingestion with Schema Drift Handling

**Role:** Data Engineer — design, build, documentation

**Description (first person):**

I built this project to show how I design ingestion pipelines that survive
real-world messy source data. NorthMart Retail Group is a fictional
retailer I created for this portfolio piece: three store systems each
export daily sales in a different schema, and those schemas drift —
renamed columns, an extra column, a missing category column, three date
formats, and currency symbols in prices. Instead of writing a separate
pipeline per file, I built one metadata-driven pipeline: a single JSON
configuration holds the source-to-target mappings, date formats, defaults,
and validation rules, and the Python pipeline reads it to ingest every
file. The pipeline detects drift in each file, coerces types, and enforces
nine validation rules covering duplicate order IDs, invalid and future
dates, quantity and price ranges, and email format. Clean rows land in one
unified silver table; bad rows are quarantined with a specific rejection
reason so nothing is silently dropped. The run processed 120 rows: 108
clean (90.0%) and 12 quarantined, with $28,855.69 of clean revenue, and I
built an Excel dashboard with live formulas and charts on top of the clean
table. Everything is documented in the README, including how the same
design maps to a Microsoft Fabric Lakehouse with PySpark. This is a
self-directed portfolio project using fictional sample data.

**Skills:** Microsoft Fabric, Data Engineering, ETL, PySpark, Python,
SQL, Data Validation, Data Modeling, Microsoft Excel, Lakehouse
Architecture

## Proposal snippet (paste into Fabric / pipeline proposals)

I'd approach your Fabric ingestion the same way I built my metadata-driven
lakehouse pipeline: one configuration drives the mappings, date handling,
and validation rules, so a new source or a renamed column is a config
change, not a rebuild. In that project I handled three differently-shaped
sales feeds, detected schema drift per file, and quarantined bad rows with
a specific rejection reason instead of silently dropping them — 108 of 120
rows loaded clean at 90.0%, with full reporting on the rest. I can bring
the same pattern to your Lakehouse: a metadata table driving PySpark
notebooks, a clean silver layer, and a quarantine table your team can
actually act on. Happy to walk you through the repo and adapt the design
to your sources.

## LinkedIn post

New portfolio project: a metadata-driven lakehouse ingestion pipeline
that turns three messy, differently-shaped store feeds into one clean
sales table — with schema drift detection and a quarantine table for
every rejected row.

One JSON config drives the mappings, date formats, defaults, and
validation rules, so adding a store is a config change, not a rebuild.

Built as a Microsoft Fabric design pattern (Python + pandas reference
implementation), with a full README and an Excel dashboard on top.

#MicrosoftFabric #DataEngineering #ETL #PySpark #DataQuality
#Lakehouse #Python #PortfolioProject
