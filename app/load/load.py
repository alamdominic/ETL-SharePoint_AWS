import os
import pandas as pd
import logging
from sqlalchemy import text, Engine

logger = logging.getLogger(__name__)


def load_data_upsert(df: pd.DataFrame, engine: Engine) -> None:
    """
    Syncs the sanitized DataFrame atomically into the target table using UPSERT logic.

    All schema, table, and column names are read from environment variables:
        DB_TARGET_SCHEMA, PRESUPUESTO_TABLE, PRESUPUESTO_SCHEMA,
        SYNC_KEY, REQUIRED_COLUMNS, DATE_COLUMNS.

    Raises:
        RuntimeError: On any SQL error — engine.begin() applies automatic ROLLBACK.
    """
    if df.empty:
        logger.warning(
            "Fase de Carga: El DataFrame recibido está vacío. No hay datos que procesar."
        )
        return

    nombre_tabla_final = os.getenv("PRESUPUESTO_TABLE")
    esquema = os.getenv("DB_TARGET_SCHEMA")
    esquema_temp = os.getenv("PRESUPUESTO_SCHEMA")
    tabla_temporal = f"temp_{nombre_tabla_final}" if nombre_tabla_final else "temp_staging"

    sync_key = os.getenv("SYNC_KEY")
    required_cols = [c.strip() for c in os.getenv("REQUIRED_COLUMNS", "").split(",") if c.strip()]
    date_cols = {c.strip() for c in os.getenv("DATE_COLUMNS", "").split(",") if c.strip()}

    missing_vars = [
        k for k, v in {
            "PRESUPUESTO_TABLE": nombre_tabla_final,
            "DB_TARGET_SCHEMA": esquema,
            "PRESUPUESTO_SCHEMA": esquema_temp,
            "SYNC_KEY": sync_key,
            "REQUIRED_COLUMNS": required_cols or None,
        }.items()
        if not v
    ]
    if missing_vars:
        raise RuntimeError(
            f"Variables de entorno no definidas: {missing_vars}. Revisa el archivo .env."
        )

    logger.info("Iniciando fase de carga y sincronización para %d registros.", len(df))

    select_exprs = [f"{col}::DATE" if col in date_cols else col for col in required_cols]
    update_cols = [col for col in required_cols if col != sync_key]

    insert_cols_str = ", ".join(required_cols) + ", update_time"
    select_str = ", ".join(select_exprs) + ", CURRENT_TIMESTAMP"
    update_str = ",\n                    ".join([f"{col} = EXCLUDED.{col}" for col in update_cols])
    update_str += ",\n                    update_time = CURRENT_TIMESTAMP"

    try:
        with engine.begin() as conexion:
            logger.info("Paso 1/3: Creando tabla temporal en el servidor PostgreSQL...")
            df.to_sql(
                name=tabla_temporal,
                con=conexion,
                schema=esquema_temp,
                if_exists="replace",
                index=False,
            )
            logger.info(
                "Paso 2/3: Ejecutando query nativo UPSERT (Sincronización Inteligente)..."
            )
            query_upsert = text(f"""
                INSERT INTO "{esquema}"."{nombre_tabla_final}"
                ({insert_cols_str})
                SELECT {select_str}
                FROM "{esquema_temp}"."{tabla_temporal}"
                ON CONFLICT ({sync_key})
                DO UPDATE SET
                    {update_str};
            """)
            conexion.execute(query_upsert)

    except Exception as e:
        error_msg = f"CRITICAL - Fallo catastrófico en la fase de carga SQL: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    finally:
        logger.info("Paso 3/3: Limpiando tabla temporal del esquema...")
        try:
            with engine.begin() as conexion:
                conexion.execute(
                    text(f'DROP TABLE IF EXISTS "{esquema_temp}"."{tabla_temporal}";')
                )
        except Exception as cleanup_err:
            logger.error(
                "No se pudo eliminar la tabla temporal '%s.%s'. Eliminarla manualmente. error=%s",
                esquema_temp,
                tabla_temporal,
                cleanup_err,
            )

    logger.info("¡Carga exitosa! La base de datos ha confirmado el COMMIT de la transacción.")
