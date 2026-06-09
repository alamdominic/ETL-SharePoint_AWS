import logging
import os

from dotenv import load_dotenv

from .source.extract import extract_xlsx
from .transform.transform import trans_data
from .load.load import load_data_upsert
from .db.config.db_config import create_db_engine
from .azure.obtain_xlsx import obtain_xlsx

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,  # force=True reemplaza handlers existentes (necesario en Lambda)
)
logger = logging.getLogger(__name__)


def run_etl() -> None:
    """
    Orquesta las tres fases del ETL en orden:
    1. Extracción: lee el archivo Excel desde PRESUPUESTO_EXCEL_PATH.
    2. Transformación: limpia, valida y normaliza el DataFrame.
    3. Carga: sincroniza los datos en la tabla destino via UPSERT atómico.

    Raises:
        RuntimeError: si PRESUPUESTO_EXCEL_PATH no está definida o el engine de DB no se pudo crear.
    """
    logger.info("=== ETL Pipeline — Inicio ===")

    # Fase 1: Extracción
    file_path = obtain_xlsx()
    df = extract_xlsx(file_path)

    # Fase 2: Transformación
    df, duplicados = trans_data(df)

    if duplicados:
        sync_key = os.getenv("SYNC_KEY", "sync_key")
        logger.warning(
            "REPORTE DE CALIDAD — %d '%s' duplicados ignorados del Excel: %s",
            len(duplicados),
            sync_key,
            duplicados,
        )

    # Fase 3: Carga
    engine = create_db_engine()
    if engine is None:
        raise RuntimeError(
            "No se pudo crear el engine de base de datos. Verifica variables DB_HOST, DB_USER, DB_PASSWORD, DB_NAME."
        )

    load_data_upsert(df, engine)

    logger.info("=== ETL Pipeline — Completado ===")


if __name__ == "__main__":
    run_etl()
