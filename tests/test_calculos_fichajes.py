"""Tests del servicio de cálculo de horas."""

from datetime import date, datetime, time, timezone

import pytest

from app.extensiones import db
from app.modelos import Empleado, RegistroJornada, Usuario
from app.fichajes.calculos import clasificar_dia, construir_segmentos_trabajo
from app.constantes import TipoRegistroJornada


@pytest.fixture
def empleado_con_usuario(aplicacion):
    with aplicacion.app_context():
        u = Usuario(correo_electronico="calc@test.local", rol="empleado", activo=True)
        u.establecer_contrasena("x")
        db.session.add(u)
        db.session.flush()
        e = Empleado(
            usuario_id=u.id,
            codigo_empleado="C99",
            nombre="T",
            apellidos="Test",
            fecha_alta=date.today(),
            horas_semanales=40,
            vacaciones_anuales=22,
            saldo_vacaciones=22,
            activo=True,
        )
        db.session.add(e)
        db.session.commit()
        eid = e.id
    return eid


def test_segmentos_entrada_salida(aplicacion, empleado_con_usuario):
    with aplicacion.app_context():
        d = date(2026, 3, 10)
        t0 = datetime.combine(d, time(9, 0), tzinfo=timezone.utc)
        t1 = datetime.combine(d, time(18, 0), tzinfo=timezone.utc)
        db.session.add(
            RegistroJornada(
                empleado_id=empleado_con_usuario,
                tipo_registro=TipoRegistroJornada.ENTRADA,
                fecha_hora_servidor=t0,
                origen="web_empleado",
                estado="valido",
            )
        )
        db.session.add(
            RegistroJornada(
                empleado_id=empleado_con_usuario,
                tipo_registro=TipoRegistroJornada.SALIDA,
                fecha_hora_servidor=t1,
                origen="web_empleado",
                estado="valido",
            )
        )
        db.session.commit()

    with aplicacion.app_context():
        from app.fichajes.calculos import obtener_registros_dia

        regs = obtener_registros_dia(empleado_con_usuario, d)
        segs = construir_segmentos_trabajo(regs)
        assert len(segs) == 1
        assert abs(segs[0].fin - segs[0].inicio).total_seconds() == 9 * 3600


def test_clasificar_dia_sin_festivo(aplicacion, empleado_con_usuario):
    with aplicacion.app_context():
        d = date(2026, 3, 11)
        res = clasificar_dia(empleado_con_usuario, d)
        assert res["horas_trabajadas"] >= 0
