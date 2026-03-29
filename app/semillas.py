"""
Datos de demostración. Ejecutar con `python scripts/cargar_demo.py` en contexto de app.

Usuarios demo: superadmin, manager, empleado (contraseña Demo1234!).
El identificador de acceso se guarda en la columna `correo_electronico` en minúsculas.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from app.constantes import (
    EstadoRegistroJornada,
    EstadoSolicitudVacaciones,
    OrigenRegistroJornada,
    RolUsuario,
    TipoRegistroJornada,
)
from app.extensiones import db
from app.modelos import (
    ConfiguracionHorasNocturnas,
    Empleado,
    Festivo,
    ItemPlantillaPlanificacion,
    PlanificacionSemanal,
    PlantillaPlanificacion,
    RegistroAuditoria,
    RegistroJornada,
    SolicitudVacaciones,
    Usuario,
)


def cargar_datos_demostracion() -> None:
    """Inserta tres usuarios y datos de ejemplo (idempotente por usuario superadmin)."""
    if Usuario.query.filter_by(correo_electronico="superadmin").first():
        return

    def crear_usuario(identificador: str, pwd: str, rol: str) -> Usuario:
        u = Usuario(
            correo_electronico=identificador.strip().lower(),
            rol=rol,
            activo=True,
        )
        u.establecer_contrasena(pwd)
        db.session.add(u)
        db.session.flush()
        return u

    super_u = crear_usuario("superadmin", "Demo1234!", RolUsuario.SUPERADMINISTRADOR)
    manager_u = crear_usuario("manager", "Demo1234!", RolUsuario.RESPONSABLE)
    empleado_u = crear_usuario("empleado", "Demo1234!", RolUsuario.EMPLEADO)

    hoy = date.today()

    emp_manager = Empleado(
        usuario_id=manager_u.id,
        codigo_empleado="M001",
        nombre="Mánager",
        apellidos="Demo",
        telefono="600000001",
        fecha_alta=hoy - timedelta(days=400),
        horas_semanales=Decimal("40"),
        vacaciones_anuales=22,
        saldo_vacaciones=Decimal("18"),
        activo=True,
        centro_trabajo="Oficina central",
    )
    db.session.add(emp_manager)
    db.session.flush()

    emp_trabajador = Empleado(
        usuario_id=empleado_u.id,
        codigo_empleado="E001",
        nombre="Persona",
        apellidos="Trabajadora",
        telefono="600000002",
        fecha_alta=hoy - timedelta(days=200),
        horas_semanales=Decimal("40"),
        vacaciones_anuales=22,
        saldo_vacaciones=Decimal("15"),
        activo=True,
        centro_trabajo="Oficina central",
        responsable_id=emp_manager.id,
    )
    db.session.add(emp_trabajador)
    db.session.flush()

    db.session.add(
        Festivo(
            fecha=date(hoy.year, 1, 1),
            nombre="Año Nuevo",
            ambito="nacional",
            activo=True,
        )
    )
    db.session.add(
        Festivo(
            fecha=date(hoy.year, 12, 6),
            nombre="Constitución (ejemplo)",
            ambito="nacional",
            activo=True,
        )
    )

    db.session.add(
        ConfiguracionHorasNocturnas(
            hora_inicio=time(22, 0),
            hora_fin=time(6, 0),
            activo=True,
        )
    )

    ayer = hoy - timedelta(days=1)
    base = datetime.combine(ayer, time(8, 0), tzinfo=timezone.utc)
    salida = datetime.combine(ayer, time(17, 0), tzinfo=timezone.utc)
    for tipo, ts in [
        (TipoRegistroJornada.ENTRADA, base),
        (TipoRegistroJornada.SALIDA, salida),
    ]:
        db.session.add(
            RegistroJornada(
                empleado_id=emp_trabajador.id,
                tipo_registro=tipo,
                fecha_hora_servidor=ts,
                origen=OrigenRegistroJornada.WEB_EMPLEADO,
                estado=EstadoRegistroJornada.VALIDO,
                creado_por_usuario_id=empleado_u.id,
            )
        )

    db.session.add(
        SolicitudVacaciones(
            empleado_id=emp_trabajador.id,
            fecha_inicio=hoy + timedelta(days=30),
            fecha_fin=hoy + timedelta(days=34),
            numero_dias=Decimal("5"),
            estado=EstadoSolicitudVacaciones.PENDIENTE,
            notas="Solicitud demo",
        )
    )

    lunes = hoy - timedelta(days=hoy.weekday())
    plan = PlanificacionSemanal(
        inicio_semana=lunes,
        estado="publicada",
        creado_por_usuario_id=super_u.id,
        notas="Semana demo",
    )
    db.session.add(plan)
    db.session.flush()

    tpl = PlantillaPlanificacion(
        nombre="Oficina L-V mañana",
        descripcion="Plantilla demostración",
        activo=True,
    )
    db.session.add(tpl)
    db.session.flush()

    db.session.add(
        ItemPlantillaPlanificacion(
            plantilla_id=tpl.id,
            empleado_id=emp_trabajador.id,
            dia_semana=0,
            hora_inicio=time(9, 0),
            hora_fin=time(14, 0),
        )
    )

    db.session.add(
        RegistroAuditoria(
            tipo_entidad="sistema",
            id_entidad=0,
            accion="semilla",
            usuario_actor_id=super_u.id,
            rol_actor=RolUsuario.SUPERADMINISTRADOR,
            motivo="Carga datos demostración",
            estado_nuevo_json='{"version":"1","usuarios":["superadmin","manager","empleado"]}',
            origen_cambio="script",
        )
    )

    db.session.commit()
