"""Tests del servicio de cálculo de horas."""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from app.extensiones import db
from app.modelos import Empleado, Empresa, RegistroJornada, Usuario
from app.fichajes.calculos import (
    clasificar_dia,
    construir_segmentos_trabajo,
    horas_pausa_entre_tramos,
)
from app.constantes import TipoRegistroJornada


@pytest.fixture
def empleado_con_usuario(aplicacion):
    with aplicacion.app_context():
        emp_row = Empresa(nombre="Empresa calc", activa=True)
        db.session.add(emp_row)
        db.session.flush()
        u = Usuario(correo_electronico="calc@test.local", rol="empleado", activo=True)
        u.establecer_contrasena("x")
        db.session.add(u)
        db.session.flush()
        e = Empleado(
            usuario_id=u.id,
            empresa_id=emp_row.id,
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


def test_turno_noche_horas_en_dia_entrada(aplicacion, empleado_con_usuario):
    """Entrada tarde y salida madrugada siguiente: todo el tramo cuenta el día de la entrada."""
    mad = ZoneInfo("Europe/Madrid")
    with aplicacion.app_context():
        d_entrada = date(2026, 3, 20)
        d_salida = date(2026, 3, 21)
        t_in = datetime(2026, 3, 20, 23, 0, tzinfo=mad).astimezone(timezone.utc)
        t_out = datetime(2026, 3, 21, 6, 0, tzinfo=mad).astimezone(timezone.utc)
        db.session.add(
            RegistroJornada(
                empleado_id=empleado_con_usuario,
                tipo_registro=TipoRegistroJornada.ENTRADA,
                fecha_hora_servidor=t_in,
                origen="web_empleado",
                estado="valido",
            )
        )
        db.session.add(
            RegistroJornada(
                empleado_id=empleado_con_usuario,
                tipo_registro=TipoRegistroJornada.SALIDA,
                fecha_hora_servidor=t_out,
                origen="web_empleado",
                estado="valido",
            )
        )
        db.session.commit()

    with aplicacion.app_context():
        r_entrada = clasificar_dia(empleado_con_usuario, d_entrada)
        r_salida = clasificar_dia(empleado_con_usuario, d_salida)
        assert abs(r_entrada["horas_trabajadas"] - 7.0) < 0.05
        assert r_salida["horas_trabajadas"] == 0.0


def test_pausa_entre_dos_tramos_mismo_dia(aplicacion, empleado_con_usuario):
    """9-14 y 17-19 → 3 h de pausa entre tramos."""
    with aplicacion.app_context():
        d = date(2026, 4, 1)
        marcas = [
            (9, 0, TipoRegistroJornada.ENTRADA),
            (14, 0, TipoRegistroJornada.SALIDA),
            (17, 0, TipoRegistroJornada.ENTRADA),
            (19, 0, TipoRegistroJornada.SALIDA),
        ]
        for h, m, tipo in marcas:
            db.session.add(
                RegistroJornada(
                    empleado_id=empleado_con_usuario,
                    tipo_registro=tipo,
                    fecha_hora_servidor=datetime.combine(
                        d, time(h, m), tzinfo=timezone.utc
                    ),
                    origen="web_empleado",
                    estado="valido",
                )
            )
        db.session.commit()

    with aplicacion.app_context():
        from app.fichajes.calculos import obtener_registros_dia

        regs = obtener_registros_dia(empleado_con_usuario, d)
        segs = construir_segmentos_trabajo(regs)
        assert abs(horas_pausa_entre_tramos(segs) - 3.0) < 0.01
        res = clasificar_dia(empleado_con_usuario, d)
        assert abs(res["horas_pausa"] - 3.0) < 0.01
        assert abs(res["horas_trabajadas"] - 7.0) < 0.01
