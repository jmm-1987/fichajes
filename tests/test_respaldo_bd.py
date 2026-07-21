"""Tests de respaldo e importación de base de datos (superadmin)."""

from io import BytesIO
from unittest.mock import patch

import pytest

from app.administracion.respaldo_bd import (
    ErrorRespaldoBd,
    normalizar_uri_postgresql,
)
from app.extensiones import db
from app.modelos import Usuario


def _login_superadmin(cliente):
    with cliente.application.app_context():
        admin = Usuario.query.filter_by(rol="superadministrador").first()
        if not admin:
            admin = Usuario(
                correo_electronico="superadmin",
                rol="superadministrador",
                activo=True,
            )
            admin.establecer_contrasena("Demo1234!")
            db.session.add(admin)
            db.session.commit()
        correo = admin.correo_electronico

    return cliente.post(
        "/autenticacion/iniciar-sesion",
        data={"nombre_usuario": correo, "contrasena": "Demo1234!"},
        follow_redirects=True,
    )


def test_base_datos_solo_superadmin(cliente):
    resp = cliente.get("/administracion/base-de-datos")
    assert resp.status_code in (302, 403)

    _login_superadmin(cliente)
    resp = cliente.get("/administracion/base-de-datos")
    assert resp.status_code == 200
    assert b"Exportar respaldo" in resp.data


def test_exportar_e_importar_sqlite(cliente):
    _login_superadmin(cliente)

    resp = cliente.get("/administracion/base-de-datos/exportar")
    assert resp.status_code == 200
    assert b"JM2 Fichajes" in resp.data
    assert "attachment" in resp.headers.get("Content-Disposition", "")

    dump = resp.data

    resp = cliente.post(
        "/administracion/base-de-datos/importar",
        data={
            "confirmar": "1",
            "fichero_respaldo": (BytesIO(dump), "respaldo.sql"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"importada correctamente" in resp.data


def test_normalizar_uri_postgresql():
    uri = "postgresql+psycopg2://user:pass@127.0.0.1:5432/fichajes"
    assert normalizar_uri_postgresql(uri) == (
        "postgresql://user:pass@127.0.0.1:5432/fichajes"
    )


def test_rechaza_respaldo_sqlite_en_postgresql(aplicacion):
    with aplicacion.app_context():
        aplicacion.config["SQLALCHEMY_DATABASE_URI"] = (
            "postgresql+psycopg2://user:pass@localhost/fichajes"
        )
        from app.administracion.respaldo_bd import _validar_contenido_sql

        dump_sqlite = (
            "-- JM2 Fichajes — respaldo completo\n"
            "-- Motor: SQLite\n"
            "PRAGMA foreign_keys=OFF;\n"
            "CREATE TABLE usuarios (id INTEGER);\n"
        )
        with pytest.raises(ErrorRespaldoBd, match="SQLite"):
            _validar_contenido_sql(dump_sqlite)


def test_exportar_postgresql_usa_pg_dump(aplicacion):
    with aplicacion.app_context():
        aplicacion.config["SQLALCHEMY_DATABASE_URI"] = (
            "postgresql+psycopg2://user:pass@127.0.0.1:5432/fichajes"
        )
        from app.administracion.respaldo_bd import exportar_bd

        class Resultado:
            returncode = 0
            stdout = "CREATE TABLE usuarios (id integer);\n"
            stderr = ""

        with patch("app.administracion.respaldo_bd.subprocess.run") as mock_run:
            mock_run.return_value = Resultado()
            contenido, nombre = exportar_bd()

        assert nombre.endswith(".sql")
        assert b"Motor: PostgreSQL" in contenido
        assert b"PRAGMA" not in contenido
        args = mock_run.call_args[0][0]
        assert args[0] == "pg_dump"
        assert args[1] == "postgresql://user:pass@127.0.0.1:5432/fichajes"
        assert "--clean" in args
        assert "--if-exists" in args
