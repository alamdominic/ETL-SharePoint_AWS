import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

from app.app_etl import run_etl  # module-level import — reused across warm invocations

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Guard against re-fetching secrets on Lambda warm container reuse.
_secrets_loaded = False


def _load_secrets() -> None:
    """Fetch DB and Azure credentials from Secrets Manager and inject into os.environ.

    Reads two Lambda env vars that point to secret names:
        SECRET_NAME_DB    — JSON secret with DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
        SECRET_NAME_AZURE — JSON secret with SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID,
                            SHAREPOINT_CLIENT_SECRET, SHAREPOINT_DRIVE_ID, SHAREPOINT_ITEM_ID

    Uses os.environ.setdefault so that explicit Lambda env vars always take precedence.
    """
    global _secrets_loaded
    if _secrets_loaded:
        return

    client = boto3.client("secretsmanager")

    for env_var in ("SECRET_NAME_DB", "SECRET_NAME_AZURE"):
        secret_name = os.environ.get(env_var)
        if not secret_name:
            raise RuntimeError(
                f"Lambda environment variable not configured: {env_var}. "
                "Set it to the name of the corresponding AWS Secrets Manager secret."
            )

        try:
            response = client.get_secret_value(SecretId=secret_name)
        except ClientError as exc:
            raise RuntimeError(
                f"Failed to retrieve secret '{secret_name}' from Secrets Manager: {exc}"
            ) from exc

        secrets: dict = json.loads(response["SecretString"])

        for key, value in secrets.items():
            os.environ.setdefault(key, str(value))

        logger.info("Secrets loaded from: %s", secret_name)

    _secrets_loaded = True


def _cleanup_tmp() -> None:
    """Remove the downloaded Excel file from /tmp after the ETL completes.

    Only acts on paths inside /tmp to avoid accidental deletion in local runs.
    """
    excel_path = os.environ.get(
        "PRESUPUESTO_EXCEL_PATH", "/tmp/PresupuestoIniciativas.xlsx"
    )
    if excel_path.startswith("/tmp/") and os.path.exists(excel_path):
        try:
            os.remove(excel_path)
            logger.info("Temp file removed: %s", excel_path)
        except OSError as exc:
            logger.warning("Could not remove temp file %s: %s", excel_path, exc)


def lambda_handler(event, context):
    """AWS Lambda entry point.

    Invoked by EventBridge on schedule (or manually).
    Loads credentials from Secrets Manager, runs the ETL pipeline,
    cleans up /tmp, and returns a structured response.

    Args:
        event:   EventBridge event payload (unused by ETL logic).
        context: Lambda context object (provides aws_request_id for tracing).

    Returns:
        dict with statusCode 200 on success, 500 on failure.
    """
    request_id = getattr(context, "aws_request_id", "local")
    function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "local")

    logger.info(
        "ETL start | function=%s | request_id=%s",
        function_name,
        request_id,
    )

    try:
        _load_secrets()
        run_etl()

        logger.info("ETL completed successfully | request_id=%s", request_id)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "success",
                "message": "ETL completed successfully",
                "requestId": request_id,
            }),
        }

    except Exception as exc:
        logger.error(
            "ETL failed | request_id=%s | error=%s",
            request_id,
            str(exc),
            exc_info=True,
        )
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": str(exc),
                "requestId": request_id,
            }),
        }

    finally:
        _cleanup_tmp()
