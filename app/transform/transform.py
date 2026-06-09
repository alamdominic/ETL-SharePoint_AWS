import pandas as pd
import logging

from .clean_columns import limpiar_columnas
from .validate import validar_columnas_obligatorias
from .sanitize import sanitizar_id_sync
from .dates import formatear_fechas
from .business_rules import aplicar_reglas_negocio

logger = logging.getLogger(__name__)


def trans_data(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Orquesta la transformación completa del DataFrame:
    1. Limpia y normaliza nombres de columnas.
    2. Valida presencia de columnas obligatorias.
    3. Sanitiza id_sync removiendo filas basura y detectando duplicados.
    4. Valida y formatea fechas a YYYY-MM-DD.
    5. Aplica reglas de negocio (ceil en montos).

    Returns:
        df: DataFrame transformado y listo para carga.
        duplicados: Lista de id_sync duplicados encontrados en el Excel (puede ser vacía).
    """
    logger.info("Iniciando fase de transformación y limpieza de datos.")

    df = limpiar_columnas(df)
    validar_columnas_obligatorias(df)
    df, duplicados = sanitizar_id_sync(df)
    df = formatear_fechas(df)
    df = aplicar_reglas_negocio(df)

    logger.info(f"Transformación completada con éxito. {len(df)} filas listas para el proceso de carga.")
    return df, duplicados
