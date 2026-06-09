import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def validar_columnas_obligatorias(df: pd.DataFrame) -> None:
    """
    Verifica que todas las columnas definidas en REQUIRED_COLUMNS existan en el DataFrame.
    Aborta el ETL inmediatamente si falta alguna.
    """
    COLUMNAS_REQUERIDAS = [
        c.strip() for c in os.getenv("REQUIRED_COLUMNS", "").split(",") if c.strip()
    ]

    faltantes = [col for col in COLUMNAS_REQUERIDAS if col not in df.columns]

    if faltantes:
        error_msg = (
            f"CRITICAL - Estructura Inválida: El archivo Excel está incompleto o corrupto. "
            f"Faltan las siguientes columnas obligatorias: {faltantes}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(
        "Validación de estructura exitosa: Las %d columnas obligatorias están presentes.",
        len(COLUMNAS_REQUERIDAS),
    )
