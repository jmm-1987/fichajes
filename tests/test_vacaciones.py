"""Reglas de solapes de vacaciones."""

from datetime import date

import pytest

from app.extensiones import db
from app.modelos import Empleado, Empresa, SolicitudVacaciones, Usuario
from app.constantes import EstadoSolicitudVacaciones
from app.vacaciones.servicios import crear_solicitud, editar_solicitud, hay_solape


@pytest.fixture
def emp_v(aplicacion):
    with aplicacion.app_context():
        empresa = Empresa(nombre="Empresa vacaciones", activa=True)
        db.session.add(empresa)
        db.session.flush()
        u = Usuario(
            correo_electronico="vac@test.local",
            rol="empleado",
            activo=True,
            empresa_id=empresa.id,
        )
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
            empresa_id=empresa.id,
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


def test_editar_solicitud_ajusta_saldo(aplicacion, emp_v):
    with aplicacion.app_context():
        sol = crear_solicitud(
            emp_v,
            date(2026, 9, 1),
            date(2026, 9, 5),
            "manual",
            estado_inicial=EstadoSolicitudVacaciones.APROBADO,
        )
        emp = Empleado.query.get(emp_v)
        emp.saldo_vacaciones = float(emp.saldo_vacaciones) - float(sol.numero_dias)
        db.session.commit()
        saldo_tras_alta = float(emp.saldo_vacaciones)

        ok, msg = editar_solicitud(
            sol.id,
            date(2026, 9, 1),
            date(2026, 9, 3),
            EstadoSolicitudVacaciones.APROBADO,
            "acortado",
        )
        assert ok, msg
        emp = Empleado.query.get(emp_v)
        sol = SolicitudVacaciones.query.get(sol.id)
        assert float(sol.numero_dias) == 3.0
        assert float(emp.saldo_vacaciones) == saldo_tras_alta + 2.0
