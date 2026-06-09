# 🔗 Conexión a Azure Entra ID — Microsoft Graph API

> Guía detallada paso a paso para autenticar una aplicación de forma desatendida (sin usuario activo) contra **Azure Entra ID** y consumir archivos de **SharePoint Online** mediante **Microsoft Graph**.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Auth](https://img.shields.io/badge/Auth-Client%20Credentials-1F3864)
![API](https://img.shields.io/badge/API-Microsoft%20Graph-2E75B6)

---

## 📋 Requisitos Previos

- Python **3.9 o superior** instalado.
- Cuenta corporativa con acceso al **portal de Azure** de la organización.
- Permisos de lectura en el sitio de SharePoint de origen.
- Un administrador de Entra ID disponible (necesario para el consentimiento del paso 1.4).

```bash
pip install msal requests python-dotenv
```

---

## ⚙️ Fase 1: Configuración en Azure Entra ID (Portal)

El objetivo de esta fase es crear una **identidad de servicio** (App Registration) que represente al script. Esta identidad tendrá su propio "usuario y contraseña" (Client ID + Client Secret) para autenticarse sin intervención humana.

### 1.1 Registrar la aplicación

1. Entra a **https://portal.azure.com** e inicia sesión con tu cuenta corporativa.
2. En la barra de búsqueda superior, escribe **"Entra ID"** (antes Azure Active Directory) y haz clic en el servicio **Microsoft Entra ID**.
3. En el menú lateral izquierdo, haz clic en **Registros de aplicaciones** (_App registrations_).
4. Haz clic en el botón **+ Nuevo registro** (parte superior).
5. Llena el formulario:
   - **Nombre:** un nombre descriptivo del proceso, ej. `ETL-AWS-Sharepoint`.
   - **Tipos de cuenta compatibles:** selecciona **"Solo las cuentas de este directorio organizativo"** (Single tenant). 🔒 Esto evita que cuentas externas puedan usar la app.
   - **URI de redirección:** déjalo **vacío** (no aplica para procesos en segundo plano).
6. Haz clic en **Registrar**.
7. Serás redirigido a la página **Información general** (_Overview_) de la app. **Copia y guarda** estos dos valores (los necesitarás en el `.env`):
   - **Id. de aplicación (cliente)** → será tu `SHAREPOINT_CLIENT_ID`
   - **Id. de directorio (inquilino)** → será tu `SHAREPOINT_TENANT_ID`

### 1.2 Generar el Client Secret (la "contraseña" de la app)

1. Dentro de tu aplicación recién creada, en el menú lateral izquierdo haz clic en **Certificados y secretos**.
2. Asegúrate de estar en la pestaña **Secretos de cliente** (_Client secrets_).
3. Haz clic en **+ Nuevo secreto de cliente**.
4. Se abrirá un panel a la derecha:
   - **Descripción:** algo identificable, ej. `secret-etl-prod`.
   - **Expira:** elige la vigencia según la política de tu organización (ej. 180 días o 24 meses). 📅 Agenda un recordatorio para rotarlo antes de que expire, o el ETL dejará de autenticar.
5. Haz clic en **Agregar**.
6. ⚠️ **CONTROL CRÍTICO — lee esto antes de salir de la pantalla:**
   - La tabla mostrará dos columnas: **Valor** (_Value_) e **Id. de secreto** (_Secret ID_).
   - Copia **INMEDIATAMENTE** el contenido de la columna **Valor** usando el ícono de copiar 📋. Este es el `SHAREPOINT_CLIENT_SECRET`.
   - El **Valor solo es visible en este momento**. Si recargas la página o sales, quedará oculto para siempre y tendrás que crear un secreto nuevo.

> 💡 **Error más común de toda la integración:** copiar el **Id. de secreto** en lugar del **Valor**. El _Id. de secreto_ es solo un identificador interno de Azure y **NO autentica**. Si tu script devuelve `invalid_client`, casi seguro copiaste la columna equivocada.

### 1.3 Asignar permisos de Microsoft Graph

1. En el menú lateral izquierdo de la app, haz clic en **Permisos de API** (_API permissions_).
2. Haz clic en **+ Agregar un permiso**.
3. En el panel derecho, selecciona la tarjeta grande de **Microsoft Graph**.
4. Azure preguntará el tipo de permiso. Selecciona **Permisos de aplicación** (_Application permissions_) — **NO** "Permisos delegados".
   - 🧠 **¿Por qué?** Los permisos _delegados_ requieren un usuario humano con sesión iniciada. Los permisos de _aplicación_ permiten que el proceso corra en segundo plano de forma autónoma (caso ETL).
5. En el buscador de permisos, escribe `Sites`.
6. Expande la categoría **Sites** y marca la casilla:
   - ✅ **`Sites.Read.All`** — recomendado para producción bajo el **principio de menor privilegio** (el ETL solo lee, no escribe).
   - _Nota: si TI lo aprueba durante desarrollo, pueden usarse scopes extendidos (`Sites.ReadWrite.All` / `Sites.FullControl.All`) para acelerar pruebas, pero deben retirarse antes de producción._
7. Haz clic en el botón **Agregar permisos** (parte inferior).

### 1.4 Conceder consentimiento de administrador

1. De regreso en la pantalla de **Permisos de API**, verás tu permiso `Sites.Read.All` con estado **"No concedido"** (ícono ⚠️ naranja/gris).
2. Haz clic en el botón **✔ Conceder consentimiento de administrador para [Tu Organización]** (junto a "+ Agregar un permiso").
   - 🔑 Este botón solo está habilitado si tu cuenta tiene rol de **administrador**. Si aparece deshabilitado, pide a un admin de Entra ID que entre a esta misma pantalla y lo haga.
3. Confirma el diálogo con **Sí**.
4. Verifica que la columna **Estado** cambió a un **círculo verde** ✅ con la leyenda **"Concedido para [Organización]"**.

> Sin este paso, el token se genera pero Graph responderá `403 Forbidden` en cada llamada.

### 1.5 Obtener los IDs de SharePoint (Graph Explorer)

Para descargar un archivo necesitas tres identificadores: `site_id`, `drive_id` e `item_id`. La forma visual de obtenerlos:

1. Entra a **https://developer.microsoft.com/graph/graph-explorer** e inicia sesión con tu cuenta corporativa.
2. **Obtener el `site_id`** — ejecuta (método `GET`):
   ```
   https://graph.microsoft.com/v1.0/sites/{tu-tenant}.sharepoint.com:/sites/{nombre-del-sitio}
   ```
   Copia el campo `id` de la respuesta JSON.
3. **Obtener el `drive_id`** — lista las bibliotecas de documentos del sitio:
   ```
   https://graph.microsoft.com/v1.0/sites/{site_id}/drives
   ```
   Copia el `id` del drive donde vive tu archivo (normalmente "Documentos" / "Documents").
4. **Obtener el `item_id`** — navega los archivos hijos de una carpeta conocida:
   ```
   https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_item_id}/children
   ```
   (Para la raíz usa `/drives/{drive_id}/root/children`). Ubica tu archivo Excel por su `name` y copia su `id`.

---

## 🔐 Fase 2: Configuración del entorno (`.env`)

Las credenciales **jamás** se escriben en el código fuente (_hardcoding_). Crea un archivo llamado `.env` en la **raíz del proyecto** con esta estructura:

```env
# ==========================================
# CREDENCIALES DE AUTENTICACIÓN (AZURE ENTRA ID)
# ==========================================
SHAREPOINT_TENANT_ID=tu_id_de_directorio_inquilino      # Paso 1.1 → "Id. de directorio"
SHAREPOINT_CLIENT_ID=tu_id_de_aplicacion_cliente        # Paso 1.1 → "Id. de aplicación"
SHAREPOINT_CLIENT_SECRET=el_VALOR_del_secreto           # Paso 1.2 → columna "Valor"

# ==========================================
# CONFIGURACIÓN DE ORIGEN (MICROSOFT GRAPH / SHAREPOINT)
# ==========================================
SHAREPOINT_SITE_ID=id_del_sitio                         # Paso 1.5.2
SHAREPOINT_DRIVE_ID=id_del_drive                        # Paso 1.5.3
SHAREPOINT_ITEM_ID=id_del_item_excel                    # Paso 1.5.4
```

> 🛡️ Agrega `.env` a tu `.gitignore` para que nunca llegue al repositorio.

---

## 🚀 Fase 3: Validación de la conexión

El proceso se valida en **dos pasos aislados** para facilitar el diagnóstico de errores: primero la autenticación, después la descarga.

### Paso 1 — Validar el handshake de autenticación (`test_auth.py`)

Aísla la conexión con Azure usando la librería oficial `msal`. Si esto funciona, tus credenciales del `.env` son correctas.

```python
import os
from dotenv import load_dotenv
import msal

# Forzar la carga real del archivo .env ignorando caché de terminal
load_dotenv(override=True)

tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
client_id = os.getenv("SHAREPOINT_CLIENT_ID")
client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")

authority = f"https://login.microsoftonline.com/{tenant_id}"

app = msal.ConfidentialClientApplication(
    client_id,
    authority=authority,
    client_credential=client_secret
)

scopes = ["https://graph.microsoft.com/.default"]

print("Solicitando token a Azure...")
result = app.acquire_token_for_client(scopes=scopes)

if "access_token" in result:
    print("¡Éxito! Token generado correctamente.")
    print(f"Token (truncado): {result['access_token'][:50]}...")
else:
    print("❌ Error al generar el token:")
    print(result.get("error_description"))
```

```bash
python test_auth.py
```

✅ **Resultado esperado:** `¡Éxito! Token generado correctamente.`

### Paso 2 — Validar la descarga del archivo (`test_download.py`)

Con la autenticación asegurada, este script consume el flujo binario de Graph y deposita el Excel localmente.

```python
import os
from dotenv import load_dotenv
import msal
import requests

# Cargar la configuración limpia del entorno
load_dotenv(override=True)

tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
client_id = os.getenv("SHAREPOINT_CLIENT_ID")
client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
drive_id = os.getenv("SHAREPOINT_DRIVE_ID")
item_id = os.getenv("SHAREPOINT_ITEM_ID")

# Ruta donde se alojará temporalmente el archivo
output_path = "app/source/temp_presupuesto.xlsx"
os.makedirs(os.path.dirname(output_path), exist_ok=True)

# 1. Obtener Token de Acceso
authority = f"https://login.microsoftonline.com/{tenant_id}"
app = msal.ConfidentialClientApplication(client_id, authority=authority, client_credential=client_secret)
token_result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

if "access_token" not in token_result:
    print("❌ Error crítico de autenticación en Azure")
    exit(1)

access_token = token_result["access_token"]

# 2. Consumo del Endpoint de Descarga
download_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
headers = {"Authorization": f"Bearer {access_token}"}

print("⬇️ Intentando descargar el archivo Excel desde SharePoint...")
response = requests.get(download_url, headers=headers, stream=True)

# 3. Escritura Binaria del Flujo
if response.status_code == 200:
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("\n=======================================================")
    print("¡ÉXITO TOTAL! Integración local validada con Graph API.")
    print(f"Archivo guardado localmente en: {output_path}")
    print(f"Tamaño del archivo: {os.path.getsize(output_path)} bytes")
    print("=======================================================")
else:
    print(f"\n❌ Fallo en la descarga. Código HTTP: {response.status_code}")
    print(response.text)
```

```bash
python test_download.py
```

✅ **Resultado esperado:** `¡ÉXITO TOTAL! Integración local validada con Graph API.`

---

## 🧠 Troubleshooting (Lecciones Aprendidas)

| Problema                                            | Causa raíz                                                                        | Solución                                                                        |
| --------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `invalid_client` al pedir token                     | Se copió el **Id. de secreto** en lugar del **Valor**                             | Crear un secreto nuevo (paso 1.2) y copiar la columna **Valor**                 |
| `403 Forbidden` en llamadas a Graph                 | Falta el consentimiento de administrador                                          | Repetir paso 1.4 y verificar el círculo verde ✅                                |
| El `.env` actualizado no surte efecto               | `python-dotenv` no sobrescribe variables ya inicializadas en la terminal          | Usar siempre `load_dotenv(override=True)` en fase de pruebas                    |
| El archivo descargado tiene otro nombre             | El endpoint `/content` envía bytes crudos sin metadatos de nombre (efecto espejo) | El nombre local lo define **únicamente** tu variable `output_path`              |
| No encuentro el `item_id` del archivo               | Navegación manual difícil en Graph                                                | Usar Graph Explorer con `.../drives/{drive_id}/items/{folder_item_id}/children` |
| Token funcionaba y dejó de autenticar meses después | El Client Secret venció                                                           | Rotar el secreto (paso 1.2) antes de su fecha de expiración                     |

---

## 📚 Referencias

- [Microsoft Graph API — Documentación oficial](https://learn.microsoft.com/graph/overview)
- [MSAL para Python](https://learn.microsoft.com/entra/msal/python/)
- [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer)
- [Registro de aplicaciones en Entra ID](https://learn.microsoft.com/entra/identity-platform/quickstart-register-app)
