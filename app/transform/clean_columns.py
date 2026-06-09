import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def limpiar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia y normaliza los nombres de columnas del DataFrame.

    1. Remueve espacios fantasmas de los nombres de columna.
    2. Renombra columna específica según COLUMN_RENAME_MAP (formato: Original Name|new_name).
    3. Estandariza a minúsculas con guiones bajos y remueve eñes.
    4. Elimina columnas temporales definidas en DROP_COLUMNS.
    """
    df = df.copy()

    df.columns = df.columns.astype(str).str.strip()

    rename_raw = os.getenv("COLUMN_RENAME_MAP", "")
    if rename_raw and "|" in rename_raw:
        src, dst = rename_raw.split("|", 1)
        src, dst = src.strip(), dst.strip()
        df = df.rename(columns={src: dst})
        logger.info("Columna '%s' mapeada a '%s'.", src, dst)

    df.columns = df.columns.str.lower().str.replace(" ", "_")
    df.columns = df.columns.str.replace("año", "ano")
    logger.info("Columnas normalizadas: %s", list(df.columns))

    delete_cols = [c.strip() for c in os.getenv("DROP_COLUMNS", "").split(",") if c.strip()]
    df = df.drop(columns=delete_cols, errors="ignore")
    if delete_cols:
        logger.info("Columnas temporales eliminadas: %s", delete_cols)

    return df
