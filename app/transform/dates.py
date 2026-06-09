import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def formatear_fechas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Valida y formatea las columnas definidas en DATE_COLUMNS a string YYYY-MM-DD.
    Aborta el ETL si existen fechas nulas o inválidas.
    """
    COLUMNAS_FECHA = [
        c.strip() for c in os.getenv("DATE_COLUMNS", "").split(",") if c.strip()
    ]

    df = df.copy()

    for col in COLUMNAS_FECHA:
        if col not in df.columns:
            continue

        df[col] = pd.to_datetime(df[col], errors="coerce")

        nulos = df[col].isna().sum()
        if nulos > 0:
            error_msg = (
                f"CRITICAL - Error de Integridad: Se encontraron {nulos} filas con fechas vacías "
                f"o inválidas en la columna '{col}'. Debido a la restricción 'DATE NOT NULL' en Postgres, "
                f"el ETL se aborta inmediatamente."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        df[col] = df[col].dt.strftime("%Y-%m-%d")

    logger.info("Formateo de fechas completado. Registros listos para 'DATE NOT NULL' (%Y-%m-%d).")
    return df
