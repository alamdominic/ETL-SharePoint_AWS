# Deployment Guide — ETL SharePoint → PostgreSQL on AWS Lambda

This guide enables any engineer to deploy this ETL from scratch.
Template-ready: swap placeholder values for a new project.

---

## Table of Contents

1. [Local Setup](#1-local-setup)
2. [Environment Variables](#2-environment-variables)
3. [Azure Configuration](#3-azure-configuration)
4. [AWS Configuration](#4-aws-configuration)
5. [Deployment](#5-deployment)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Local Setup

### Python Version

Python **3.12** is required (matches the Lambda runtime).

```bash
python --version   # must be 3.12.x
```

### Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

> **Local testing of `lambda_handler.py`** also requires `boto3`:
> ```bash
> pip install boto3
> ```
> `boto3` is pre-installed in the Lambda base image and excluded from `requirements.txt`
> to avoid shipping a redundant copy inside the container.

### Run Locally (without Lambda)

```bash
python app.py
```

Requires a populated `.env` file (see Section 2).

---

## 2. Environment Variables

### Local Development (`.env` file)

Copy `.env.example` to `.env` and fill in all values.

```bash
cp .env.example .env
```

**Never commit `.env` to version control.** `.gitignore` already excludes it.

### Complete Variable Reference

#### PostgreSQL — Connection

| Variable | Required | Description |
|---|:---:|---|
| `DB_HOST` | Yes | PostgreSQL server hostname or IP |
| `DB_PORT` | No | Port (default: `5432`) |
| `DB_NAME` | Yes | Database name |
| `DB_USER` | Yes | Database user |
| `DB_PASSWORD` | Yes | User password (URL-encoded automatically) |

#### PostgreSQL — Target

| Variable | Required | Description |
|---|:---:|---|
| `PRESUPUESTO_SCHEMA` | Yes | Schema for staging and target table |
| `DB_TARGET_SCHEMA` | Yes | Schema for the final target table |
| `PRESUPUESTO_TABLE` | Yes | Target table name |

#### Excel Source

| Variable | Required | Description |
|---|:---:|---|
| `PRESUPUESTO_EXCEL_PATH` | No | Destination path for downloaded file. Auto-detects `/tmp/PresupuestoIniciativas.xlsx` in Lambda. |
| `EXCEL_SHEET` | Yes | Sheet name inside the Excel file (e.g., `Hoja 1`) |

#### Azure / SharePoint

| Variable | Required | Description |
|---|:---:|---|
| `SHAREPOINT_TENANT_ID` | Yes | Azure Entra ID tenant (directory) ID |
| `SHAREPOINT_CLIENT_ID` | Yes | App registration client (application) ID |
| `SHAREPOINT_CLIENT_SECRET` | Yes | Client secret value |
| `SHAREPOINT_DRIVE_ID` | Yes | SharePoint drive ID containing the Excel file |
| `SHAREPOINT_ITEM_ID` | Yes | Item (file) ID of the Excel in SharePoint |

#### Data Transformation

| Variable | Required | Description |
|---|:---:|---|
| `SYNC_KEY` | Yes | Column name used as the UPSERT primary key (e.g., `id_sync`) |
| `REQUIRED_COLUMNS` | Yes | Comma-separated list of columns that must exist in the Excel |
| `DATE_COLUMNS` | Yes | Comma-separated columns to format as `YYYY-MM-DD` |
| `CEIL_COLUMNS` | Yes | Comma-separated numeric columns to apply `ceil()` |
| `COLUMN_RENAME_MAP` | No | `Original Name\|new_name` pairs, pipe-separated between pairs |
| `DROP_COLUMNS` | No | Comma-separated columns to remove after rename |

#### AWS Secrets Manager (Lambda only)

| Variable | Required | Description |
|---|:---:|---|
| `SECRET_NAME_DB` | Yes | Name of the Secrets Manager secret containing DB credentials |
| `SECRET_NAME_AZURE` | Yes | Name of the Secrets Manager secret containing Azure credentials |

### Example `.env` (generic)

```env
# ── Database ──────────────────────────────────────────────────────────────────
DB_HOST=
DB_PORT=5432
DB_NAME=
DB_USER=
DB_PASSWORD=

# ── Target schema / table ─────────────────────────────────────────────────────
PRESUPUESTO_SCHEMA=
DB_TARGET_SCHEMA=
PRESUPUESTO_TABLE=

# ── Excel source ──────────────────────────────────────────────────────────────
PRESUPUESTO_EXCEL_PATH=
EXCEL_SHEET=Hoja 1

# ── Azure Entra ID / SharePoint ───────────────────────────────────────────────
SHAREPOINT_TENANT_ID=
SHAREPOINT_CLIENT_ID=
SHAREPOINT_CLIENT_SECRET=
SHAREPOINT_DRIVE_ID=
SHAREPOINT_ITEM_ID=

# ── Transformation rules ──────────────────────────────────────────────────────
SYNC_KEY=
REQUIRED_COLUMNS=
DATE_COLUMNS=
CEIL_COLUMNS=
COLUMN_RENAME_MAP=
DROP_COLUMNS=
```

---

## 3. Azure Configuration

For detailed step-by-step Azure setup see `app/azure/conection.md`.

### Summary

1. **App Registration** — Create an application in Azure Entra ID (portal.azure.com → Entra ID → App registrations → New registration).
2. **Client Secret** — Generate under Certificates & Secrets → Client secrets. Copy the **Value** column immediately (hidden after page reload).
3. **API Permissions** — Add `Microsoft Graph → Application permissions → Sites.Read.All`. Grant admin consent.
4. **SharePoint IDs** — Use Graph Explorer to retrieve `drive_id` and `item_id` for the target Excel file.

### Minimum Required Permissions

| Permission | Type | Reason |
|---|---|---|
| `Sites.Read.All` | Application | Read SharePoint files without an interactive user |

---

## 4. AWS Configuration

### 4.1 IAM Role for Lambda

Create a role named (example) `lambda-etl-presupuesto-role` with these policies:

#### Managed policies (attach)

- `AWSLambdaBasicExecutionRole` — Writes logs to CloudWatch

#### Inline policy — Secrets Manager read

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": [
        "arn:aws:secretsmanager:<REGION>:<ACCOUNT_ID>:secret:<SECRET_NAME_DB>*",
        "arn:aws:secretsmanager:<REGION>:<ACCOUNT_ID>:secret:<SECRET_NAME_AZURE>*"
      ]
    }
  ]
}
```

> Replace `<REGION>`, `<ACCOUNT_ID>`, `<SECRET_NAME_DB>`, `<SECRET_NAME_AZURE>` with actual values.

#### VPC (conditional)

If RDS is in a private VPC, also attach `AWSLambdaVPCAccessExecutionRole` and configure Lambda with the correct subnets and security groups. Ensure the Lambda security group has outbound access to the RDS security group on port 5432, and outbound HTTPS (443) to reach Secrets Manager and Microsoft Graph.

### 4.2 Secrets Manager — Create Secrets

Create two secrets via AWS Console or CLI.

**Secret 1 — Database credentials**

Secret name: choose a name and set it as `SECRET_NAME_DB` in Lambda env vars.

```json
{
  "DB_HOST": "<rds-endpoint>",
  "DB_PORT": "5432",
  "DB_NAME": "<database-name>",
  "DB_USER": "<db-user>",
  "DB_PASSWORD": "<db-password>"
}
```

**Secret 2 — Azure credentials**

Secret name: choose a name and set it as `SECRET_NAME_AZURE` in Lambda env vars.

```json
{
  "SHAREPOINT_TENANT_ID": "<tenant-id>",
  "SHAREPOINT_CLIENT_ID": "<client-id>",
  "SHAREPOINT_CLIENT_SECRET": "<client-secret-value>",
  "SHAREPOINT_DRIVE_ID": "<drive-id>",
  "SHAREPOINT_ITEM_ID": "<item-id>"
}
```

CLI equivalent:

```bash
aws secretsmanager create-secret \
  --name "<SECRET_NAME_DB>" \
  --description "ETL Presupuesto Iniciativas — DB credentials" \
  --secret-string '{"DB_HOST":"...","DB_PORT":"5432","DB_NAME":"...","DB_USER":"...","DB_PASSWORD":"..."}'

aws secretsmanager create-secret \
  --name "<SECRET_NAME_AZURE>" \
  --description "ETL Presupuesto Iniciativas — Azure credentials" \
  --secret-string '{"SHAREPOINT_TENANT_ID":"...","SHAREPOINT_CLIENT_ID":"...","SHAREPOINT_CLIENT_SECRET":"...","SHAREPOINT_DRIVE_ID":"...","SHAREPOINT_ITEM_ID":"..."}'
```

### 4.3 ECR — Container Registry

```bash
# Create repository
aws ecr create-repository \
  --repository-name <ECR_REPO_NAME> \
  --region <REGION>

# Authenticate Docker to ECR
aws ecr get-login-password --region <REGION> \
  | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
```

### 4.4 Lambda Function — Configuration

| Setting | Value |
|---|---|
| Runtime | Container image |
| Architecture | x86_64 |
| Handler | (defined in image CMD — `lambda_handler.lambda_handler`) |
| Memory | 512 MB minimum (pandas + Excel processing) |
| Timeout | 300 seconds (5 minutes) — adjust based on file size |
| Execution role | IAM role from Section 4.1 |
| Ephemeral storage (/tmp) | 512 MB default — increase if Excel file exceeds ~400 MB |

#### Lambda Environment Variables (non-sensitive)

Set these directly on the Lambda function configuration:

```
PRESUPUESTO_EXCEL_PATH    = /tmp/PresupuestoIniciativas.xlsx
EXCEL_SHEET               = Hoja 1
PRESUPUESTO_SCHEMA        = <staging-schema>
DB_TARGET_SCHEMA          = <target-schema>
PRESUPUESTO_TABLE         = <target-table>
SYNC_KEY                  = id_sync
REQUIRED_COLUMNS          = id_sync,fecha,fecha_comp_aa,sucursal,iniciativas,base
DATE_COLUMNS              = fecha,fecha_comp_aa
CEIL_COLUMNS              = base,iniciativas
COLUMN_RENAME_MAP         = Fecha comparación año anterior|fecha_comp_aa
DROP_COLUMNS              = mes,ano
SECRET_NAME_DB            = <name-of-db-secret-in-secrets-manager>
SECRET_NAME_AZURE         = <name-of-azure-secret-in-secrets-manager>
```

### 4.5 EventBridge — Schedule Trigger

```bash
# Create rule (example: daily at 06:00 UTC)
aws events put-rule \
  --name "etl-presupuesto-daily" \
  --schedule-expression "cron(0 6 * * ? *)" \
  --state ENABLED

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name <LAMBDA_FUNCTION_NAME> \
  --statement-id "EventBridgeDailyTrigger" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:<REGION>:<ACCOUNT_ID>:rule/etl-presupuesto-daily

# Attach Lambda as target
aws events put-targets \
  --rule "etl-presupuesto-daily" \
  --targets "Id=etl-target,Arn=arn:aws:lambda:<REGION>:<ACCOUNT_ID>:function:<LAMBDA_FUNCTION_NAME>"
```

### 4.6 CloudWatch — Log Group

Lambda creates the log group automatically on first invocation.
Name format: `/aws/lambda/<LAMBDA_FUNCTION_NAME>`

Recommended: set retention to avoid unbounded log accumulation.

```bash
aws logs put-retention-policy \
  --log-group-name "/aws/lambda/<LAMBDA_FUNCTION_NAME>" \
  --retention-in-days 30
```

To create a CloudWatch alarm for ETL failures:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "etl-presupuesto-errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --dimensions Name=FunctionName,Value=<LAMBDA_FUNCTION_NAME> \
  --statistic Sum \
  --period 86400 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:<REGION>:<ACCOUNT_ID>:<SNS_TOPIC>
```

---

## 5. Deployment

### Step 1 — Build Docker image

```bash
# From project root
docker build -t <ECR_REPO_NAME>:latest .
```

### Step 2 — Test locally (optional)

```bash
# Start Lambda emulator
docker run --rm -p 9000:8080 \
  --env-file .env \
  -e SECRET_NAME_DB=<secret-name> \
  -e SECRET_NAME_AZURE=<secret-name> \
  <ECR_REPO_NAME>:latest

# In another terminal, invoke the handler
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{}'
```

> Local invocation skips Secrets Manager. Set all credentials directly in `.env`
> or as `-e VAR=value` flags for the local test.

### Step 3 — Push to ECR

```bash
docker tag <ECR_REPO_NAME>:latest \
  <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/<ECR_REPO_NAME>:latest

docker push \
  <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/<ECR_REPO_NAME>:latest
```

### Step 4 — Create or Update Lambda

**First deployment:**

```bash
aws lambda create-function \
  --function-name <LAMBDA_FUNCTION_NAME> \
  --package-type Image \
  --code ImageUri=<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/<ECR_REPO_NAME>:latest \
  --role arn:aws:iam::<ACCOUNT_ID>:role/<IAM_ROLE_NAME> \
  --memory-size 512 \
  --timeout 300 \
  --environment "Variables={PRESUPUESTO_EXCEL_PATH=/tmp/PresupuestoIniciativas.xlsx,EXCEL_SHEET=Hoja 1,...}"
```

**Update after new image push:**

```bash
aws lambda update-function-code \
  --function-name <LAMBDA_FUNCTION_NAME> \
  --image-uri <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/<ECR_REPO_NAME>:latest
```

### Step 5 — Test Lambda invocation

```bash
aws lambda invoke \
  --function-name <LAMBDA_FUNCTION_NAME> \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json
# Expected: {"statusCode": 200, "body": "{\"status\": \"success\", ...}"}
```

### Step 6 — Verify logs in CloudWatch

```bash
aws logs tail "/aws/lambda/<LAMBDA_FUNCTION_NAME>" --follow
```

Expected log sequence:
```
ETL start | function=<name> | request_id=<uuid>
Secrets loaded from: <SECRET_NAME_DB>
Secrets loaded from: <SECRET_NAME_AZURE>
=== ETL Pipeline — Inicio ===
Token Azure obtenido correctamente.
Archivo descargado exitosamente. path=/tmp/PresupuestoIniciativas.xlsx ...
...
=== ETL Pipeline — Completado ===
Temp file removed: /tmp/PresupuestoIniciativas.xlsx
ETL completed successfully | request_id=<uuid>
```

---

## 6. Troubleshooting

| Error | Cause | Solution |
|---|---|---|
| `RuntimeError: Lambda environment variable not configured: SECRET_NAME_DB` | Lambda env var missing | Add `SECRET_NAME_DB` to Lambda configuration |
| `Failed to retrieve secret ... AccessDeniedException` | IAM role lacks Secrets Manager permission | Add inline policy from Section 4.1 |
| `RuntimeError: Variables de entorno faltantes: [...]` | Secret JSON missing a key | Verify the secret in Secrets Manager has all required keys |
| `RuntimeError: Autenticación Azure fallida: ...` | Invalid/expired client secret | Rotate the secret in Azure Entra ID and update Secrets Manager |
| `requests.HTTPError: Descarga fallida con status 403` | Admin consent not granted for Graph API | Repeat consent grant in Azure portal (Section 3, step 3) |
| `FileNotFoundError: Excel not found at /tmp/...` | `obtain_xlsx()` failed silently | Check CloudWatch logs for the download step; verify Azure credentials |
| `Task timed out after 300.00 seconds` | ETL exceeded Lambda timeout | Increase timeout (max 900s) or investigate slow DB/network |
| `MemoryError` / `OOM` | pandas loading large Excel | Increase Lambda memory (up to 10240 MB) |
| `/tmp` write failed | Ephemeral storage exceeded 512 MB | Increase `/tmp` size in Lambda configuration (up to 10240 MB) |
| `psycopg2.OperationalError: could not connect to server` | Lambda not in same VPC as RDS, or security group blocks port 5432 | Configure Lambda VPC (Section 4.1) |
| `ValueError: Null dates found in column ...` | Excel contains empty or invalid date cells | Fix source data in SharePoint; date columns must be fully populated |
| `ValueError: Columnas obligatorias faltantes: [...]` | Excel structure changed | Update `REQUIRED_COLUMNS` env var or fix source file |

### Rotating Secrets

When DB passwords or Azure client secrets expire:

1. Update the value in the source system (DB or Azure portal).
2. Update the Secrets Manager secret:
   ```bash
   aws secretsmanager update-secret \
     --secret-id <SECRET_NAME> \
     --secret-string '{"key": "new-value", ...}'
   ```
3. No Lambda redeploy needed — secrets are fetched at runtime.

### Force re-reading secrets on warm container

`lambda_handler.py` caches secrets after first load to avoid Secrets Manager calls on every warm invocation. If you update a secret and need it picked up immediately without waiting for a cold start:

```bash
aws lambda update-function-configuration \
  --function-name <LAMBDA_FUNCTION_NAME> \
  --description "force cold start $(date)"
```

This triggers a new cold start on the next invocation.
