"""Flujo de registro de marca con validación."""

from datetime import date

import pytest

from app.extensiones import db
from app.modelos import Empleado, Usuario
from app.fichajes.servicios import registrar_marca
from app.constantes import TipoRegistroJornada, OrigenRegistroJornada


@pytest.fixture
def emp_id(aplicacion):
    with aplicacion.app_context():
        u = Usuario(correo_electronico="fich@test.local", rol="empleado", activo=True)
        u.establecer_contrasena("x")
        db.session.add(u)
        db.session.flush()
        e = Empleado(
            usuario_id=u.id,
            codigo_empleado="F01",
            nombre="F",
            apellidos="Flujo",
            fecha_alta=date.today(),
            horas_semanales=40,
            vacaciones_anuales=22,
            saldo_vacaciones=22,
            activo=True,
        )
        db.session.add(e)
        db.session.commit()
        return e.id


def test_registrar_entrada_y_salida(aplicacion, emp_id):
    with aplicacion.app_context():
        emp = Empleado.query.get(emp_id)
        uid = emp.usuario_id
        with aplicacion.test_request_context("/"):
            r1, err = registrar_marca(
                emp_id,
                TipoRegistroJornada.ENTRADA,
                usuario_id=uid,
                origen=OrigenRegistroJornada.WEB_EMPLEADO,
                validar_secuencia=True,
            )
            assert err is None
            assert r1 is not None
            r2, err2 = registrar_marca(
                emp_id,
                TipoRegistroJornada.SALIDA,
                usuario_id=uid,
                origen=OrigenRegistroJornada.WEB_EMPLEADO,
                validar_secuencia=True,
            )
            assert err2 is None
