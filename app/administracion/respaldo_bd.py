"""Exportación e importación completa de la base de datos (solo superadmin)."""

import re
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app

from app.extensiones import db


class ErrorRespaldoBd(Exception):
    """Error operativo en exportación o importación."""


_MARCADOR_RESPALDO = "JM2 Fichajes — respaldo completo"
_TAMANO_MAX_IMPORTACION = 500 * 1024 * 1024  # 500 MB


def _uri_bd() -> str:
    return current_app.config.get("SQLALCHEMY_DATABASE_URI", "")


def es_sqlite(uri: str | None = None) -> bool:
    uri = uri or _uri_bd()
    return uri.startswith("sqlite:")


def es_postgresql(uri: str | None = None) -> bool:
    uri = uri or _uri_bd()
    return uri.startswith("postgresql") or uri.startswith("postgres://")


def motor_bd(uri: str | None = None) -> str:
    """Nombre del motor actual (SQLite o PostgreSQL)."""
    uri = uri or _uri_bd()
    if es_sqlite(uri):
        return "SQLite"
    if es_postgresql(uri):
        return "PostgreSQL"
    raise ErrorRespaldoBd("Tipo de base de datos no soportado para respaldo.")


def normalizar_uri_postgresql(uri: str) -> str:
    """
    Convierte la URI SQLAlchemy (`postgresql+psycopg2://...`) a una URI estándar
    aceptada por pg_dump y psql.
    """
    if uri.startswith("postgres://"):
        uri = "postgresql://" + uri[len("postgres://") :]
    return re.sub(r"^postgresql\+[^:]+://", "postgresql://", uri)


def _ruta_sqlite(uri: str) -> Path | None:
    """Ruta del fichero SQLite, o None si es base en memoria."""
    if not es_sqlite(uri):
        return None
    if uri in ("sqlite:///:memory:", "sqlite://"):
        return None
    if uri.endswith(":memory:"):
        return None
    return Path(uri.replace("sqlite:///", "", 1))


def _cabecera_respaldo(motor: str) -> str:
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lineas = [
        f"-- {_MARCADOR_RESPALDO}",
        f"-- Generado: {ahora}",
        f"-- Motor: {motor}",
    ]
    if motor == "SQLite":
        lineas.append("PRAGMA foreign_keys=OFF;")
    return "\n".join(lineas) + "\n"


def _pie_respaldo(motor: str) -> str:
    if motor == "SQLite":
        return "PRAGMA foreign_keys=ON;\n"
    return ""


def _motor_en_respaldo(contenido: str) -> str | None:
    coincidencia = re.search(r"--\s*Motor:\s*(\w+)", contenido, flags=re.IGNORECASE)
    return coincidencia.group(1) if coincidencia else None


def exportar_bd() -> tuple[bytes, str]:
    """
    Exporta la BD completa a un único fichero SQL de texto.
    Devuelve (contenido, nombre_fichero).
    """
    uri = _uri_bd()
    marca = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    nombre = f"fichajes_respaldo_{marca}.sql"

    if es_sqlite(uri):
        contenido = _exportar_sqlite(uri)
    elif es_postgresql(uri):
        contenido = _exportar_postgresql(uri)
    else:
        raise ErrorRespaldoBd("Tipo de base de datos no soportado para respaldo.")

    return contenido.encode("utf-8"), nombre


def _exportar_sqlite(uri: str) -> str:
    ruta = _ruta_sqlite(uri)
    if ruta is not None:
        if not ruta.exists():
            raise ErrorRespaldoBd("No se encontró el fichero de base de datos.")
        conn = sqlite3.connect(str(ruta))
        try:
            lineas = list(conn.iterdump())
        finally:
            conn.close()
    else:
        raw = db.engine.raw_connection()
        try:
            lineas = list(raw.iterdump())
        finally:
            raw.close()

    motor = "SQLite"
    return _cabecera_respaldo(motor) + "\n".join(lineas) + "\n" + _pie_respaldo(motor)


def _exportar_postgresql(uri: str) -> str:
    uri_cli = normalizar_uri_postgresql(uri)
    try:
        resultado = subprocess.run(
            [
                "pg_dump",
                uri_cli,
                "--format=plain",
                "--no-owner",
                "--no-privileges",
                "--clean",
                "--if-exists",
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ErrorRespaldoBd(
            "No se encontró pg_dump. En el servidor instale el cliente PostgreSQL "
            "(paquete postgresql-client)."
        ) from exc

    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout or "").strip()
        raise ErrorRespaldoBd(f"No se pudo exportar la base de datos: {detalle}")

    motor = "PostgreSQL"
    return _cabecera_respaldo(motor) + resultado.stdout + _pie_respaldo(motor)


def _validar_contenido_sql(contenido: str) -> None:
    if not contenido or not contenido.strip():
        raise ErrorRespaldoBd("El fichero está vacío.")

    if len(contenido.encode("utf-8")) > _TAMANO_MAX_IMPORTACION:
        raise ErrorRespaldoBd(
            "El fichero supera el tamaño máximo permitido (500 MB)."
        )

    texto = contenido.strip().lower()
    if not (
        _MARCADOR_RESPALDO.lower() in texto
        or re.search(r"\b(create\s+table|insert\s+into)\b", texto)
    ):
        raise ErrorRespaldoBd(
            "El fichero no parece un respaldo SQL válido de esta aplicación."
        )

    motor_actual = motor_bd()
    motor_respaldo = _motor_en_respaldo(contenido)
    if motor_respaldo:
        if motor_respaldo.lower() != motor_actual.lower():
            raise ErrorRespaldoBd(
                f"El respaldo es de {motor_respaldo} pero la aplicación usa "
                f"{motor_actual}. No se puede importar entre motores distintos."
            )
    elif motor_actual == "PostgreSQL" and "pragma foreign_keys" in texto:
        raise ErrorRespaldoBd(
            "El fichero parece un respaldo SQLite. En producción (PostgreSQL) "
            "solo se pueden importar respaldos generados desde PostgreSQL."
        )


def importar_bd(contenido: bytes) -> None:
    """Restaura la BD completa desde un fichero SQL de respaldo."""
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ErrorRespaldoBd("El fichero debe estar codificado en UTF-8.") from exc

    _validar_contenido_sql(texto)

    uri = _uri_bd()
    if es_sqlite(uri):
        _importar_sqlite(uri, texto)
    elif es_postgresql(uri):
        _importar_postgresql(uri, texto)
    else:
        raise ErrorRespaldoBd("Tipo de base de datos no soportado para importación.")

    db.session.remove()


def _importar_sqlite(uri: str, contenido: str) -> None:
    ruta = _ruta_sqlite(uri)
    db.session.remove()

    if ruta is not None:
        db.engine.dispose()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if ruta.exists():
            copia = ruta.with_suffix(ruta.suffix + ".bak")
            shutil.copy2(ruta, copia)

        if ruta.exists():
            ruta.unlink()

        conn = sqlite3.connect(str(ruta))
        try:
            conn.executescript(contenido)
            conn.commit()
        except sqlite3.Error as exc:
            raise ErrorRespaldoBd(f"Error al importar el respaldo: {exc}") from exc
        finally:
            conn.close()
        db.engine.dispose()
        return

    raw = db.engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        for (nombre_tabla,) in cursor.fetchall():
            cursor.execute(f'DROP TABLE IF EXISTS "{nombre_tabla}"')
        raw.commit()
        raw.executescript(contenido)
        raw.commit()
    except sqlite3.Error as exc:
        raw.rollback()
        raise ErrorRespaldoBd(f"Error al importar el respaldo: {exc}") from exc
    finally:
        raw.close()


def _importar_postgresql(uri: str, contenido: str) -> None:
    uri_cli = normalizar_uri_postgresql(uri)
    db.session.remove()
    db.engine.dispose()

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".sql",
        encoding="utf-8",
        delete=False,
    ) as fichero:
        fichero.write(contenido)
        ruta_tmp = fichero.name

    try:
        try:
            resultado = subprocess.run(
                [
                    "psql",
                    uri_cli,
                    "-v",
                    "ON_ERROR_STOP=1",
                    "--single-transaction",
                    "-f",
                    ruta_tmp,
                ],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ErrorRespaldoBd(
                "No se encontró psql. En el servidor instale el cliente PostgreSQL "
                "(paquete postgresql-client)."
            ) from exc

        if resultado.returncode != 0:
            detalle = (resultado.stderr or resultado.stdout or "").strip()
            raise ErrorRespaldoBd(f"Error al importar el respaldo: {detalle}")
    finally:
        Path(ruta_tmp).unlink(missing_ok=True)

    db.engine.dispose()
