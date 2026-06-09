import os
import pandas as pd
import logging

# Configuración básica del logging (conecta con tu estructura de data/logs/)
logger = logging.getLogger(__name__)


def extract_xlsx(file_path: str) -> pd.DataFrame:
    """
    Busca el archivo Excel de presupuesto, lo lee de forma segura
    y lo monta en memoria como un DataFrame de Pandas.

    Validaciones:
    - Verifica la existencia del archivo.
    - Captura errores si el archivo está dañado o abierto por un usuario (bloqueado).
    """
    logger.info(f"Iniciando fase de extracción. Buscando archivo en: {file_path}")

    # 1. Validación de existencia
    if not os.path.exists(file_path):
        error_msg = f"Error de Extracción: El archivo no existe en la ruta especificada: '{file_path}'"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # os.getenv siempre retorna string; convertir a int si el valor es numérico (índice de hoja)
    sheet_raw = os.getenv("EXCEL_SHEET")
    if sheet_raw is None:
        sheet = 0
    elif sheet_raw.strip().isdigit():
        sheet = int(sheet_raw.strip())
    else:
        sheet = sheet_raw

    try:
        # 2. Procesamiento: Lectura del archivo usando openpyxl como engine para archivos .xlsx
        # Usamos un bloque 'with' indirecto o el manejo nativo de pandas para evitar bloqueos
        df = pd.read_excel(file_path, sheet_name=sheet, engine="openpyxl")

        if df.empty or len(df.columns) == 0:
            # Listar hojas disponibles para diagnóstico
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            available_sheets = wb.sheetnames
            wb.close()
            logger.error(
                "Excel leído pero DataFrame vacío. sheet_usado=%s hojas_disponibles=%s. "
                "Ajusta la variable EXCEL_SHEET.",
                sheet,
                available_sheets,
            )
            raise ValueError(
                f"Sheet '{sheet}' está vacía. Hojas disponibles: {available_sheets}. "
                f"Define EXCEL_SHEET con el nombre o índice correcto."
            )

        logger.info(
            "Extracción exitosa. Se cargaron %d filas y %d columnas en memoria.",
            len(df),
            len(df.columns),
        )
        return df

    except PermissionError as e:
        error_msg = f"Error de Extracción: No se puede acceder al archivo. Es probable que esté abierto por otro usuario o bloqueado. Detalles: {e}"
        logger.error(error_msg)
        raise PermissionError(error_msg)

    except ValueError as e:
        logger.error("Error de Extracción (hoja '%s'): %s", sheet, e)
        raise

    except Exception as e:
        error_msg = f"Error de Extracción: El archivo Excel está dañado o no se puede procesar. Detalles: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
