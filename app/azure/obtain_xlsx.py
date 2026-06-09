import logging
import os

import msal
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

logger = logging.getLogger(__name__)

# Timeouts en segundos para la descarga: (conexión, lectura)
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 120

# Reintentos automáticos ante fallos de red transitorios (backoff: 1s, 2s, 4s)
_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,  # el status se valida manualmente más abajo
)


def _build_session() -> requests.Session:
    """Crea sesión HTTP con reintentos y keep-alive para Graph API."""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=_RETRY_STRATEGY)
    session.mount("https://", adapter)
    return session


def obtain_xlsx() -> str:
    """Download the Excel file from SharePoint via Microsoft Graph API.

    Reads Azure / SharePoint config from environment variables, authenticates
    using MSAL client-credentials flow, and writes the file to disk.

    Environment variables required:
        SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET,
        SHAREPOINT_DRIVE_ID, SHAREPOINT_ITEM_ID

    Optional:
        PRESUPUESTO_EXCEL_PATH  — destination path (default: app/source/source_file.xlsx).
                                  Use /tmp/source_file.xlsx for AWS Lambda / ECS.

    Returns:
        str: Absolute-or-relative path where the file was saved.

    Raises:
        RuntimeError: If required env vars are missing or Azure auth fails.
        requests.HTTPError: If the Graph API download returns a non-200 status.
    """
    # 1. Cargar y validar variables de entorno obligatorias
    tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
    client_id = os.getenv("SHAREPOINT_CLIENT_ID")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
    drive_id = os.getenv("SHAREPOINT_DRIVE_ID")
    item_id = os.getenv("SHAREPOINT_ITEM_ID")

    missing = [
        name
        for name, val in {
            "SHAREPOINT_TENANT_ID": tenant_id,
            "SHAREPOINT_CLIENT_ID": client_id,
            "SHAREPOINT_CLIENT_SECRET": client_secret,
            "SHAREPOINT_DRIVE_ID": drive_id,
            "SHAREPOINT_ITEM_ID": item_id,
        }.items()
        if not val
    ]
    if missing:
        logger.error("Variables de entorno faltantes: %s", missing)
        raise RuntimeError(f"Variables de entorno faltantes: {missing}")

    # Ruta destino del archivo Excel.
    # Local: ruta absoluta al archivo    → C:\path\to\file.xlsx
    # AWS Lambda / ECS: /tmp/source_file.xlsx
    output_path = os.getenv(
        "PRESUPUESTO_EXCEL_PATH", "app/source/source_file.xlsx"
    )

    # abspath garantiza que dirname nunca sea "" (caso: solo nombre de archivo sin directorio)
    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)

    # 2. Autenticación MSAL (Client Credentials Flow)
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    msal_app = msal.ConfidentialClientApplication(
        client_id, authority=authority, client_credential=client_secret
    )

    token_result = msal_app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )

    if "access_token" not in token_result:
        error_desc = token_result.get("error_description", "sin descripción")
        logger.error("Fallo de autenticación Azure. error=%s", error_desc)
        print("❌ Error crítico de autenticación en Azure:")
        print(error_desc)
        raise RuntimeError(f"Autenticación Azure fallida: {error_desc}")

    logger.info("Token Azure obtenido correctamente.")
    access_token = token_result["access_token"]

    # 3. Descarga vía Microsoft Graph con timeout y reintentos configurados
    download_url = (
        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
    )
    headers = {"Authorization": f"Bearer {access_token}"}

    logger.info(
        "Descargando archivo desde SharePoint. drive_id=%s item_id=%s", drive_id, item_id
    )
    print("⬇️ Intentando descargar el archivo Excel desde SharePoint...")

    session = _build_session()
    try:
        # 4. Validación de la respuesta y escritura binaria en chunks
        with session.get(
            download_url,
            headers=headers,
            stream=True,
            timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
        ) as response:
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                file_size = os.path.getsize(output_path)
                logger.info(
                    "Archivo descargado exitosamente. path=%s size_bytes=%d",
                    output_path,
                    file_size,
                )
                print("\n=======================================================")
                print("¡ÉXITO TOTAL! Integración local validada con Graph API.")
                print(f"Archivo guardado en: {output_path}")
                print(f"Tamaño del archivo descargado: {file_size} bytes")
                print("=======================================================")
                return output_path

            logger.error(
                "Fallo en descarga de SharePoint. status=%d response=%s",
                response.status_code,
                response.text,
            )
            print(f"\n❌ Fallo en la descarga. Código HTTP de Graph: {response.status_code}")
            print("Respuesta detallada del servidor de Microsoft:")
            print(response.text)
            raise requests.HTTPError(
                f"Descarga fallida con status {response.status_code}: {response.text}"
            )
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    obtain_xlsx()
