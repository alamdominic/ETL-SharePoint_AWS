import os
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def aplicar_reglas_negocio(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica reglas de negocio: convierte a numérico y redondea hacia arriba (ceil)
    las columnas definidas en CEIL_COLUMNS.
    """
    COLUMNAS_CEIL = [
        c.strip() for c in os.getenv("CEIL_COLUMNS", "").split(",") if c.strip()
    ]

    df = df.copy()

    for col in COLUMNAS_CEIL:
        if col not in df.columns:
            continue

        df[col] = pd.to_numeric(df[col], errors="coerce")

        nulos_post_coerce = df[col].isna().sum()
        if nulos_post_coerce > 0:
            logger.warning(
                "Columna '%s' tiene %d valores no numéricos convertidos a NaN. "
                "Si la columna es NOT NULL en PostgreSQL, el UPSERT fallará.",
                col,
                nulos_post_coerce,
            )

        df[col] = df[col].where(df[col].isna(), np.ceil(df[col]))
        logger.info("Regla de negocio aplicada: columna '%s' redondeada hacia arriba.", col)

    return df
