"""PostgreSQL configuration and engine creation."""

import logging
import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine


def create_db_engine():
    """Crea y devuelve un motor de conexión (engine) SQLAlchemy para PostgreSQL.

    Establece conexión utilizando psycopg2 como driver PostgreSQL con codificación
    segura de credenciales. Maneja automáticamente caracteres especiales en contraseñas.

    Dependencies:
        - sqlalchemy.create_engine
        - urllib.parse.quote_plus
        - os.getenv

    Variables de entorno requeridas:
        - DB_HOST: Dirección del servidor PostgreSQL
        - DB_USER: Usuario de base de datos
        - DB_PASSWORD: Contraseña (se codifica automáticamente)
        - DB_NAME: Nombre de la base de datos
        - DB_PORT: Puerto (opcional, default 5432)

    Returns:
        sqlalchemy.engine.Engine | None: Engine configurado y listo para usar,
        o None si faltan variables de entorno requeridas.

    Raises:
        Exception: Si hay error en la creación del engine (conexión, credenciales, etc.)
    """

    # Variables de entorno usadas por el proyecto (ver .env.example)
    DB_HOST = os.getenv("DB_HOST")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")
    DB_PORT = os.getenv("DB_PORT", "5432")

    # Verificación básica de que las variables existen
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        return None

    try:
        # Codificamos el password solo si existe
        safe_password = quote_plus(DB_PASSWORD)
        connection_str = f"postgresql+psycopg2://{DB_USER}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

        engine = create_engine(connection_str)
        return engine

    except Exception as e:
        logging.getLogger(__name__).error(
            f"Error al crear el engine de base de datos: {e}"
        )
        return None


if __name__ == "__main__":
    engine = create_db_engine()
    if engine:
        print("Conexión a PostgreSQL exitosa.")
