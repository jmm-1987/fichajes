"""Reglas de solapes de vacaciones."""

from datetime import date

import pytest

from app.extensiones import db
from app.modelos import Empleado, SolicitudVacaciones, Usuario
from app.constantes import EstadoSolicitudVacaciones
from app.vacaciones.servicios import hay_solape, crear_solicitud


@pytest.fixture
def emp_v(aplicacion):
    with aplicacion.app_context():
        u = Usuario(correo_electronico="vac@test.local", rol="empleado", activo=True)
        u.establecer_contrasena("x")
        db.session.add(u)
        db.session.flush()
        e = Empleado(
            usuario_id=u.id,
            codigo_empleado="V01",
            nombre="V",
            apellidos="Vac",
            fecha_alta=date.today(),
            horas_semanales=40,
            vacaciones_anuales=22,
            saldo_vacaciones=22,
            activo=True,
        )
        db.session.add(e)
        db.session.commit()
        return e.id


def test_solape_detectado(aplicacion, emp_v):
    with aplicacion.app_context():
        s = SolicitudVacaciones(
            empleado_id=emp_v,
            fecha_inicio=date(2026, 7, 1),
            fecha_fin=date(2026, 7, 10),
            numero_dias=10,
            estado=EstadoSolicitudVacaciones.APROBADO,
        )
        db.session.add(s)
        db.session.commit()
        assert hay_solape(emp_v, date(2026, 7, 5), date(2026, 7, 6)) is True


def test_crear_sin_solape(aplicacion, emp_v):
    with aplicacion.app_context():
        sol = crear_solicitud(
            emp_v,
            date(2026, 8, 1),
            date(2026, 8, 5),
            None,
        )
        assert sol is not None
