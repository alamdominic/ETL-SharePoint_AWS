import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def sanitizar_id_sync(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Limpia la columna definida en SYNC_KEY eliminando filas vacías o basura de fórmulas
    arrastradas en Excel. Detecta duplicados, los reporta y conserva solo la última ocurrencia.

    Returns:
        df: DataFrame limpio y sin duplicados en la clave de sincronización.
        duplicados: Lista de valores duplicados encontrados.
    """
    sync_key = os.getenv("SYNC_KEY", "id_sync")

    if sync_key not in df.columns:
        return df, []

    df = df.copy()
    df[sync_key] = df[sync_key].astype(str).str.strip()

    df = df[
        df[sync_key].notna()
        & (df[sync_key] != "")
        & (df[sync_key] != "nan")
    ]
    logger.info("Filtro '%s' aplicado: Se removieron arrastres de fórmulas vacías.", sync_key)

    duplicados: list[str] = (
        df[df.duplicated(subset=[sync_key], keep=False)][sync_key]
        .unique()
        .tolist()
    )

    if duplicados:
        logger.warning(
            "DUPLICADOS DETECTADOS: %d '%s' aparecen más de una vez en el Excel. "
            "Se conserva la última ocurrencia de cada uno. IDs afectados: %s",
            len(duplicados),
            sync_key,
            duplicados,
        )
        df = df.drop_duplicates(subset=[sync_key], keep="last")

    return df, duplicados
