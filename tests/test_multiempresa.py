from app.constantes import RolUsuario
from app.extensiones import db
from app.modelos import Empleado, Empresa, Usuario


def _crear_usuario_empleado(correo: str, rol: str, empresa: Empresa) -> Empleado:
    u = Usuario(correo_electronico=correo, rol=rol, activo=True, empresa_id=empresa.id)
    u.establecer_contrasena("Demo1234!")
    db.session.add(u)
    db.session.flush()
    e = Empleado(
        usuario_id=u.id,
        codigo_empleado=correo,
        nombre="Nombre",
        apellidos="Apellidos",
        fecha_alta=db.func.current_date(),
        horas_semanales=40,
        vacaciones_anuales=22,
        saldo_vacaciones=22,
        activo=True,
        empresa_id=empresa.id,
    )
    db.session.add(e)
    db.session.commit()
    return e


def test_responsable_no_ve_empleados_otra_empresa(aplicacion, cliente):
    with aplicacion.app_context():
        emp_a = Empresa(nombre="Empresa A", activa=True)
        emp_b = Empresa(nombre="Empresa B", activa=True)
        db.session.add_all([emp_a, emp_b])
        db.session.commit()

        # Responsable en empresa A
        responsable_a = _crear_usuario_empleado(
            "resp_a", RolUsuario.RESPONSABLE, emp_a
        )
        # Empleado en empresa A
        empleado_a = _crear_usuario_empleado("empl_a", RolUsuario.EMPLEADO, emp_a)
        # Empleado en empresa B
        empleado_b = _crear_usuario_empleado("empl_b", RolUsuario.EMPLEADO, emp_b)

        # Responsable A solo debería gestionar empleados de su empresa
        desde_login = cliente.post(
            "/autenticacion/iniciar-sesion",
            data={"usuario": "resp_a", "contrasena": "Demo1234!"},
            follow_redirects=True,
        )
        assert desde_login.status_code == 200

        # Puede ver detalle de empleado A
        r_ok = cliente.get(f"/empleados/{empleado_a.id}")
        assert r_ok.status_code == 200

        # No puede ver detalle de empleado B (otra empresa) -> redirige o 403
        r_forbidden = cliente.get(f"/empleados/{empleado_b.id}", follow_redirects=False)
        assert r_forbidden.status_code in (302, 403)

