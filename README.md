<div align="center">

# ETL — SharePoint AWS

**Python ETL pipeline that downloads an Excel file from SharePoint and syncs data to PostgreSQL using atomic UPSERT logic.**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-ETL-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-Graph_API-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)
![Status](https://img.shields.io/badge/Status-Production-success?style=for-the-badge)

</div>

---

## Pipeline Flow

```
☁️ SharePoint (OneDrive / SharePoint Online)
    │
    ▼  Microsoft Graph API · MSAL Client Credentials
┌─────────────────────────────────────────────────────────────────┐
│  0. DOWNLOAD        azure/obtain_xlsx.py                        │
│     Authenticates with Azure Entra ID and downloads the Excel   │
│     from SharePoint via Microsoft Graph API                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. EXTRACT         source/extract.py                           │
│     Reads the Excel file by sheet name (EXCEL_SHEET)            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. TRANSFORM       transform/                                  │
│     Normalizes columns → Validates structure → Cleans sync key  │
│     → Formats dates → Applies business rules to numeric fields  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. LOAD UPSERT     load/load.py                                │
│     INSERT ... ON CONFLICT (id_sync) DO UPDATE                  │
│     → <schema>.<target_table>                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
ETL-SharePoint-AWS/
│
├── app.py                          # Entry point
│
├── app/
│   ├── app_etl.py                  # ETL orchestrator (Download → E → T → L)
│   │
│   ├── azure/
│   │   ├── obtain_xlsx.py          # Downloads Excel from SharePoint (Graph API)
│   │   └── token_access.py         # Helper script: Azure auth handshake test
│   │
│   ├── source/
│   │   └── extract.py              # Reads Excel with pandas/openpyxl
│   │
│   ├── transform/
│   │   ├── transform.py            # Orchestrates the 5 transformation steps
│   │   ├── clean_columns.py        # Normalizes column names
│   │   ├── validate.py             # Validates required columns
│   │   ├── sanitize.py             # Removes empty/duplicate sync key rows
│   │   ├── dates.py                # Formats dates → YYYY-MM-DD
│   │   └── business_rules.py       # Applies numeric field rules
│   │
│   ├── load/
│   │   └── load.py                 # Atomic UPSERT to PostgreSQL
│   │
│   └── db/
│       └── config/
│           └── db_config.py        # SQLAlchemy engine from env vars
│
├── .env.example                    # Environment variable template
└── requirements.txt                # Project dependencies
```

---

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd ETL-SharePoint-AWS
```

### 2. Create virtual environment and install dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS
pip install -r requirements.txt
```

**Dependencies:** `pandas` · `sqlalchemy` · `psycopg2-binary` · `openpyxl` · `python-dotenv` · `msal` · `requests`

---

## Configuration

Create `.env` in the project root by copying `.env.example`:

```bash
cp .env.example .env
```

### Environment Variables

#### PostgreSQL Database

| Variable | Required | Description |
|---|:---:|---|
| `DB_HOST` | ✅ | PostgreSQL server host |
| `DB_USER` | ✅ | Database user |
| `DB_PASSWORD` | ✅ | Password (auto-encoded with `quote_plus`) |
| `DB_NAME` | ✅ | Database name |
| `DB_PORT` | ⬜ | Port (default: `5432`) |

#### PostgreSQL Destination

| Variable | Required | Description |
|---|:---:|---|
| `PRESUPUESTO_SCHEMA` | ✅ | Schema for the staging table and target table |
| `PRESUPUESTO_TABLE` | ✅ | Target table name in PostgreSQL |

#### Excel Source

| Variable | Required | Description |
|---|:---:|---|
| `PRESUPUESTO_EXCEL_PATH` | ✅ | Path where the downloaded Excel is saved. Local: absolute path. AWS/ECS: `/tmp/file.xlsx` |
| `EXCEL_SHEET` | ✅ | Exact sheet name (case and space sensitive) |

#### Azure Entra ID / SharePoint

| Variable | Required | Description |
|---|:---:|---|
| `SHAREPOINT_TENANT_ID` | ✅ | Azure Entra ID tenant ID |
| `SHAREPOINT_CLIENT_ID` | ✅ | Client ID of the registered Azure application |
| `SHAREPOINT_CLIENT_SECRET` | ✅ | Client secret of the application |
| `SHAREPOINT_DRIVE_ID` | ✅ | SharePoint drive ID where the Excel resides |
| `SHAREPOINT_ITEM_ID` | ✅ | Item (file) ID in SharePoint |

---

## Database Setup

### 1. Create the schema

```sql
CREATE SCHEMA IF NOT EXISTS <schema>;
```

### 2. Create the target table

```sql
CREATE TABLE <schema>.<target_table> (
    id_sync     VARCHAR(50)    NOT NULL,
    -- add your columns here
    update_time TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT <target_table>_pkey PRIMARY KEY (id_sync)
);
```

### 3. Grant permissions to the ETL user

```sql
GRANT USAGE  ON SCHEMA <schema>                        TO <user>;
GRANT INSERT, UPDATE ON TABLE <schema>.<target_table>  TO <user>;
GRANT CREATE, USAGE  ON SCHEMA <staging_schema>        TO <user>;
```

> The ETL creates and drops a staging table in the schema defined by `PRESUPUESTO_SCHEMA`. The user needs `CREATE` on that schema.

---

## Running

```bash
python app.py
```

### Expected logs (successful run)

```
INFO  app.app_etl           : === ETL — Start ===
INFO  app.azure.obtain_xlsx : Azure token obtained successfully.
INFO  app.azure.obtain_xlsx : Downloading file from SharePoint. drive_id=... item_id=...
INFO  app.azure.obtain_xlsx : File downloaded successfully. path=... size_bytes=...
INFO  app.source.extract    : Starting extraction. Looking for file at: ...
INFO  app.source.extract    : Extraction complete. Loaded N rows and M columns.
INFO  app.transform.transform: Starting transformation phase.
INFO  app.transform.transform: Transformation complete. N rows ready for load.
INFO  app.load.load         : Starting load phase for N records.
INFO  app.load.load         : Step 1/3: Creating staging table...
INFO  app.load.load         : Step 2/3: Executing UPSERT query...
INFO  app.load.load         : Step 3/3: Dropping staging table...
INFO  app.load.load         : Load successful. Database committed.
INFO  app.app_etl           : === ETL — Completed ===
```

---

## UPSERT Logic

The ETL **never duplicates records**. PostgreSQL decides per row:

| Case | Condition | Action |
|:---:|---|---|
| **New** | `id_sync` not in target table | Full `INSERT` |
| **Modified** | `id_sync` already exists | `UPDATE` all fields + `update_time` |

> The operation is **atomic**: if any step fails, a full `ROLLBACK` is executed. The target table is never left in a partial state.

---

## Error Handling

| Exception | Cause | Behavior |
|---|---|---|
| `RuntimeError` — missing vars | Azure or DB variables not set in `.env` | Aborts · lists missing variables |
| `RuntimeError` — Azure auth | Invalid or expired Azure credentials | Aborts · prints MSAL error description |
| `requests.HTTPError` | Graph API returns status != 200 | Aborts · logs status and server response |
| `FileNotFoundError` | Excel not found at `PRESUPUESTO_EXCEL_PATH` | Aborts · logs the path searched |
| `PermissionError` | Excel open by another user | Aborts · indicates file is locked |
| `ValueError` — empty sheet | `EXCEL_SHEET` points to empty or missing sheet | Aborts · lists available sheets |
| `ValueError` — columns | Required columns missing from Excel | Aborts before touching the DB |
| `ValueError` — dates | Null or invalid dates in Excel | Aborts · indicates column and row count affected |
| `RuntimeError` — schema | `PRESUPUESTO_SCHEMA` not set in `.env` | Aborts before connecting to DB |
| `RuntimeError` — DB | UPSERT failure | Aborts with automatic `ROLLBACK` |
