"""
Script auxiliar de verificación — NO forma parte del pipeline ETL.

Propósito: confirmar que las credenciales de Azure Entra ID (tenant_id,
client_id, client_secret) son válidas y que MSAL puede completar el
handshake con Microsoft Graph antes de desplegar el ETL en producción.

Uso: ejecutar manualmente desde la raíz del proyecto:
    python -m app.azure.token_access

No importar desde otros módulos.
"""

import os
from dotenv import load_dotenv
import msal

# 1. Cargar variables del archivo .env
load_dotenv()

tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
client_id = os.getenv("SHAREPOINT_CLIENT_ID")
client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")

# 2. Construir la URL de autenticación (Authority)
authority = f"https://login.microsoftonline.com/{tenant_id}"

# 3. Inicializar la aplicación cliente confidencial de MSAL
app = msal.ConfidentialClientApplication(
    client_id, authority=authority, client_credential=client_secret
)

# 4. Solicitar el token de acceso para Microsoft Graph (Scope por defecto para App Permissions)
scopes = ["https://graph.microsoft.com/.default"]

print("Solicitando token a Azure...")
result = app.acquire_token_for_client(scopes=scopes)

if "access_token" in result:
    print("¡Éxito! Token generado correctamente.")
    # Imprimimos solo los primeros 50 caracteres por seguridad
    print(f"Token (truncado): {result['access_token'][:50]}...")
else:
    print("Error al generar el token:")
    print(result.get("error"))
    print(result.get("error_description"))
