"""Exportación e importación completa de la base de datos (solo superadmin)."""

import re
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from flask import current_app
from sqlalchemy import inspect, text

from app.constantes import RolUsuario
from app.extensiones import db
from app.modelos import (
    Empleado,
    Empresa,
    ItemPlanificacionSemanal,
    PlantillaPlanificacion,
    Usuario,
)


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


def exportar_bd_empresa(empresa_id: int) -> tuple[bytes, str]:
    """
    Exporta un SQL restaurable (esquema + datos) con una sola empresa:
    empleados, usuarios ligados, fichajes, festivos, config y superadmins.
    Sirve para importarlo en una instancia dedicada.
    """
    empresa = db.session.get(Empresa, int(empresa_id))
    if empresa is None:
        raise ErrorRespaldoBd("No existe esa empresa.")

    alcance = _alcance_empresa(empresa.id)
    uri = _uri_bd()
    motor = motor_bd(uri)
    marca = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = _slug_archivo(empresa.nombre)
    nombre = f"fichajes_respaldo_empresa_{empresa.id}_{slug}_{marca}.sql"

    cabecera = _cabecera_respaldo_empresa(motor, empresa)
    if es_postgresql(uri):
        texto = (
            cabecera
            + _esquema_postgresql(uri)
            + _sql_datos_alcance(alcance, "postgresql")
            + _sql_secuencias_postgresql()
            + _pie_respaldo(motor)
        )
    elif es_sqlite(uri):
        texto = (
            cabecera
            + _esquema_sqlite()
            + _sql_datos_alcance(alcance, "sqlite")
            + _pie_respaldo(motor)
        )
    else:
        raise ErrorRespaldoBd("Tipo de base de datos no soportado para respaldo.")

    return texto.encode("utf-8"), nombre


def _slug_archivo(texto: str) -> str:
    limpio = re.sub(r"[^\w]+", "_", (texto or "").strip(), flags=re.UNICODE)
    return (limpio.strip("_")[:60] or "empresa")


def _cabecera_respaldo_empresa(motor: str, empresa: Empresa) -> str:
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lineas = [
        f"-- {_MARCADOR_RESPALDO}",
        f"-- Generado: {ahora}",
        f"-- Motor: {motor}",
        f"-- Empresa-id: {empresa.id}",
        f"-- Empresa: {empresa.nombre}",
        "-- Alcance: una empresa (más superadministradores).",
    ]
    if motor == "SQLite":
        lineas.append("PRAGMA foreign_keys=OFF;")
    return "\n".join(lineas) + "\n"


def _quote_ident(nombre: str) -> str:
    return '"' + str(nombre).replace('"', '""') + '"'


def _sql_in(ids: set[int]) -> str:
    if not ids:
        return "NULL"
    return ",".join(str(int(i)) for i in sorted(ids))


def _alcance_empresa(empresa_id: int) -> dict:
    eid = int(empresa_id)
    empleados = Empleado.query.filter_by(empresa_id=eid).all()
    empleado_ids = {int(e.id) for e in empleados}
    usuario_ids = {int(e.usuario_id) for e in empleados if e.usuario_id}

    for u in Usuario.query.filter(
        (Usuario.empresa_id == eid)
        | (Usuario.rol == RolUsuario.SUPERADMINISTRADOR)
    ).all():
        usuario_ids.add(int(u.id))

    plan_ids: set[int] = set()
    if empleado_ids:
        for item in ItemPlanificacionSemanal.query.filter(
            ItemPlanificacionSemanal.empleado_id.in_(empleado_ids)
        ).all():
            plan_ids.add(int(item.planificacion_semanal_id))

    plantilla_ids: set[int] = set()
    for plantilla in PlantillaPlanificacion.query.all():
        ids_en_items = {
            int(it.empleado_id)
            for it in plantilla.items
            if it.empleado_id is not None
        }
        if not ids_en_items or (ids_en_items & empleado_ids):
            plantilla_ids.add(int(plantilla.id))

    return {
        "empresa_id": eid,
        "empleado_ids": empleado_ids,
        "usuario_ids": usuario_ids,
        "planificacion_ids": plan_ids,
        "plantilla_ids": plantilla_ids,
    }


def _where_tabla(tabla: str, alcance: dict) -> str | None:
    eid = alcance["empresa_id"]
    emp_in = _sql_in(alcance["empleado_ids"])
    usr_in = _sql_in(alcance["usuario_ids"])
    plan_in = _sql_in(alcance["planificacion_ids"])
    tpl_in = _sql_in(alcance["plantilla_ids"])

    filtros = {
        "alembic_version": None,
        "empresas": f"id = {eid}",
        "usuarios": f"id IN ({usr_in})" if alcance["usuario_ids"] else "1=0",
        "empleados": f"empresa_id = {eid}",
        "festivos": f"empresa_id = {eid}",
        "configuracion_horas_nocturnas": f"empresa_id = {eid}",
        "configuracion_aplicacion": (
            f"(clave NOT LIKE 'empresa:%' OR clave LIKE 'empresa:{eid}:%')"
        ),
        "planificaciones_semanales": (
            f"id IN ({plan_in})" if alcance["planificacion_ids"] else "1=0"
        ),
        "plantillas_planificacion": (
            f"id IN ({tpl_in})" if alcance["plantilla_ids"] else "1=0"
        ),
        "registros_jornada": f"empleado_id IN ({emp_in})",
        "solicitudes_vacaciones": f"empleado_id IN ({emp_in})",
        "solicitudes_correccion": f"empleado_id IN ({emp_in})",
        "clasificaciones_dia_laboral": f"empleado_id IN ({emp_in})",
        "items_planificacion_semanal": f"empleado_id IN ({emp_in})",
        "items_plantilla_planificacion": (
            f"plantilla_id IN ({tpl_in}) AND "
            f"(empleado_id IS NULL OR empleado_id IN ({emp_in}))"
            if alcance["plantilla_ids"]
            else "1=0"
        ),
        "registros_auditoria": (
            f"(usuario_actor_id IS NULL OR usuario_actor_id IN ({usr_in}))"
            if alcance["usuario_ids"]
            else "usuario_actor_id IS NULL"
        ),
    }
    if tabla not in filtros:
        return "1=0"
    return filtros[tabla]


_ORDEN_INSERT = (
    "alembic_version",
    "empresas",
    "usuarios",
    "empleados",
    "festivos",
    "configuracion_horas_nocturnas",
    "configuracion_aplicacion",
    "planificaciones_semanales",
    "plantillas_planificacion",
    "registros_jornada",
    "solicitudes_vacaciones",
    "solicitudes_correccion",
    "clasificaciones_dia_laboral",
    "items_planificacion_semanal",
    "items_plantilla_planificacion",
    "registros_auditoria",
)


def _literal_sql(valor, dialect: str) -> str:
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        if dialect == "postgresql":
            return "TRUE" if valor else "FALSE"
        return "1" if valor else "0"
    if isinstance(valor, int) and not isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, float):
        return repr(valor)
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if isinstance(valor, datetime):
        return "'" + valor.isoformat() + "'"
    if isinstance(valor, date):
        return "'" + valor.isoformat() + "'"
    if isinstance(valor, time):
        return "'" + valor.isoformat() + "'"
    if isinstance(valor, UUID):
        return "'" + str(valor) + "'"
    if isinstance(valor, (bytes, memoryview)):
        return "'\\x" + bytes(valor).hex() + "'"
    texto = str(valor).replace("'", "''")
    if dialect == "postgresql":
        return "E'" + texto.replace("\\", "\\\\") + "'"
    return "'" + texto + "'"


def _ajustar_fila_empleado(fila: dict, alcance: dict) -> dict:
    datos = dict(fila)
    if datos.get("responsable_id") not in alcance["empleado_ids"]:
        datos["responsable_id"] = None
    if datos.get("responsable_usuario_id") not in alcance["usuario_ids"]:
        datos["responsable_usuario_id"] = None
    return datos


def _nombre_tabla_insert(tabla: str, dialect: str) -> str:
    quoted = _quote_ident(tabla)
    if dialect == "postgresql":
        return f"public.{quoted}"
    return quoted


def _sql_datos_alcance(alcance: dict, dialect: str) -> str:
    insp = inspect(db.engine)
    existentes = set(insp.get_table_names())
    partes = ["", "-- Datos filtrados por empresa", ""]
    if dialect == "postgresql":
        # pg_dump deja search_path vacío; sin esto falla INSERT INTO "alembic_version"
        partes.append("SET search_path TO public;")
        partes.append("")
    for tabla in _ORDEN_INSERT:
        if tabla not in existentes:
            continue
        where = _where_tabla(tabla, alcance)
        quoted = _quote_ident(tabla)
        sql = f"SELECT * FROM {quoted}"
        if where is not None:
            sql += f" WHERE {where}"
        filas = db.session.execute(text(sql)).mappings().all()
        if not filas:
            continue
        columnas = list(filas[0].keys())
        cols_sql = ", ".join(_quote_ident(c) for c in columnas)
        destino = _nombre_tabla_insert(tabla, dialect)
        for fila in filas:
            datos = dict(fila)
            if tabla == "empleados":
                datos = _ajustar_fila_empleado(datos, alcance)
            valores = ", ".join(_literal_sql(datos[c], dialect) for c in columnas)
            partes.append(
                f"INSERT INTO {destino} ({cols_sql}) VALUES ({valores});"
            )
        partes.append("")
    return "\n".join(partes)


def _esquema_postgresql(uri: str) -> str:
    uri_cli = normalizar_uri_postgresql(uri)
    try:
        resultado = subprocess.run(
            [
                "pg_dump",
                uri_cli,
                "--format=plain",
                "--schema-only",
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
        raise ErrorRespaldoBd(f"No se pudo exportar el esquema: {detalle}")
    return resultado.stdout + "\n"


def _sql_secuencias_postgresql() -> str:
    insp = inspect(db.engine)
    partes = ["", "-- Secuencias", "SET search_path TO public;", ""]
    for tabla in insp.get_table_names():
        pk = insp.get_pk_constraint(tabla) or {}
        cols = pk.get("constrained_columns") or []
        if cols != ["id"]:
            continue
        qtabla = f"public.{_quote_ident(tabla)}"
        partes.append(
            "SELECT setval(pg_get_serial_sequence("
            f"'public.{tabla}', 'id'), COALESCE((SELECT MAX(id) FROM {qtabla}), 1), true);"
        )
    partes.append("")
    return "\n".join(partes)


def _esquema_sqlite() -> str:
    insp = inspect(db.engine)
    nombres = insp.get_table_names()
    partes = []
    for n in reversed(nombres):
        partes.append(f"DROP TABLE IF EXISTS {_quote_ident(n)};")
    raw = db.engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"
        )
        for (sql,) in cur.fetchall():
            partes.append(sql.rstrip(";") + ";")
        cur.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type IN ('index', 'trigger') AND sql IS NOT NULL"
        )
        for (sql,) in cur.fetchall():
            partes.append(sql.rstrip(";") + ";")
    finally:
        raw.close()
    partes.append("")
    return "\n".join(partes) + "\n"
