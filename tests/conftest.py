"""Configuración pytest-flask."""

import pytest

from app import crear_aplicacion
from configuracion import ConfiguracionPruebas
from app.extensiones import db
from app.modelos import Empresa, Usuario


@pytest.fixture
def aplicacion():
    """Instancia Flask (nombre del fixture en español; evita colisión con el módulo `app`)."""
    instancia = crear_aplicacion(config_class=ConfiguracionPruebas)
    with instancia.app_context():
        db.create_all()
        yield instancia
        db.session.remove()
        db.drop_all()


@pytest.fixture
def cliente(aplicacion):
    return aplicacion.test_client()


@pytest.fixture
def usuario_ejemplo(aplicacion):
    with aplicacion.app_context():
        empresa = Empresa(nombre="Empresa test", activa=True)
        db.session.add(empresa)
        db.session.flush()
        u = Usuario(
            correo_electronico="test@test.local",
            rol="empleado",
            activo=True,
            empresa_id=empresa.id,
        )
        u.establecer_contrasena("Test1234!")
        db.session.add(u)
        db.session.commit()
        return u.id
