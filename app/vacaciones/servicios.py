"""Reglas de negocio de vacaciones."""

from datetime import date
from decimal import Decimal

from flask_login import current_user

from app.auditoria.servicios import registrar_auditoria
from app.constantes import EstadoSolicitudVacaciones, TipoAccionAuditoria
from app.extensiones import db
from app.modelos import Empleado, SolicitudVacaciones


def contar_dias_laborables(inicio: date, fin: date) -> float:
    """Cuenta días naturales en el rango (inclusive). Simplificación: días corridos."""
    if fin < inicio:
        return 0.0
    return float((fin - inicio).days + 1)


def hay_solape(empleado_id: int, ini: date, fin: date, excluir_id: int | None = None) -> bool:
    """True si existe solicitud aprobada o pendiente que solape."""
    q = SolicitudVacaciones.query.filter(
        SolicitudVacaciones.empleado_id == empleado_id,
        SolicitudVacaciones.estado.in_(
            (
                EstadoSolicitudVacaciones.PENDIENTE,
                EstadoSolicitudVacaciones.APROBADO,
                EstadoSolicitudVacaciones.DISFRUTADO,
            )
        ),
        SolicitudVacaciones.fecha_inicio <= fin,
        SolicitudVacaciones.fecha_fin >= ini,
    )
    if excluir_id:
        q = q.filter(SolicitudVacaciones.id != excluir_id)
    return q.first() is not None


def crear_solicitud(
    empleado_id: int,
    fecha_inicio: date,
    fecha_fin: date,
    notas: str | None,
    estado_inicial: str = EstadoSolicitudVacaciones.PENDIENTE,
) -> SolicitudVacaciones | None:
    """Crea solicitud si no hay solape."""
    if hay_solape(empleado_id, fecha_inicio, fecha_fin):
        return None
    dias = contar_dias_laborables(fecha_inicio, fecha_fin)
    sol = SolicitudVacaciones(
        empleado_id=empleado_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        numero_dias=Decimal(str(dias)),
        estado=estado_inicial,
        notas=notas,
    )
    db.session.add(sol)
    db.session.flush()
    registrar_auditoria(
        tipo_entidad="solicitud_vacaciones",
        id_entidad=sol.id,
        accion=TipoAccionAuditoria.CREAR,
        estado_nuevo={"dias": dias, "estado": estado_inicial},
        motivo="Alta solicitud vacaciones",
    )
    db.session.commit()
    return sol


def aprobar_solicitud(solicitud_id: int, notas: str | None) -> tuple[bool, str]:
    sol = SolicitudVacaciones.query.get(solicitud_id)
    if not sol or sol.estado != EstadoSolicitudVacaciones.PENDIENTE:
        return False, "Solicitud no válida."
    emp = Empleado.query.get(sol.empleado_id)
    if not emp:
        return False, "Empleado no encontrado."
    dias = float(sol.numero_dias)
    saldo = float(emp.saldo_vacaciones)
    if saldo < dias:
        return False, "Saldo de vacaciones insuficiente."

    emp.saldo_vacaciones = Decimal(str(saldo - dias))
    sol.estado = EstadoSolicitudVacaciones.APROBADO
    sol.aprobado_por_usuario_id = current_user.id
    from app.fichajes.validadores import ahora_servidor

    sol.aprobado_en = ahora_servidor()
    sol.notas = (sol.notas or "") + ("\n" if sol.notas else "") + (notas or "")

    registrar_auditoria(
        tipo_entidad="solicitud_vacaciones",
        id_entidad=sol.id,
        accion=TipoAccionAuditoria.APROBAR,
        estado_nuevo={"estado": sol.estado},
        motivo=notas or "Aprobación",
        usuario_actor_id=current_user.id,
    )
    db.session.commit()
    return True, "Aprobada."


def rechazar_solicitud(solicitud_id: int, notas: str | None) -> tuple[bool, str]:
    sol = SolicitudVacaciones.query.get(solicitud_id)
    if not sol or sol.estado != EstadoSolicitudVacaciones.PENDIENTE:
        return False, "Solicitud no válida."
    sol.estado = EstadoSolicitudVacaciones.RECHAZADO
    sol.aprobado_por_usuario_id = current_user.id
    from app.fichajes.validadores import ahora_servidor

    sol.aprobado_en = ahora_servidor()
    sol.notas = (sol.notas or "") + ("\n" if sol.notas else "") + (notas or "")
    registrar_auditoria(
        tipo_entidad="solicitud_vacaciones",
        id_entidad=sol.id,
        accion=TipoAccionAuditoria.RECHAZAR,
        estado_nuevo={"estado": sol.estado},
        motivo=notas or "Rechazo",
        usuario_actor_id=current_user.id,
    )
    db.session.commit()
    return True, "Rechazada."


def marcar_disfrutadas_pasadas(fecha_referencia: date | None = None) -> int:
    """
    Pasa a disfrutado las aprobadas cuya fecha_fin < hoy.
    Llamar desde mantenimiento o vista admin.
    """
    hoy = fecha_referencia or date.today()
    q = SolicitudVacaciones.query.filter(
        SolicitudVacaciones.estado == EstadoSolicitudVacaciones.APROBADO,
        SolicitudVacaciones.fecha_fin < hoy,
    )
    n = 0
    for sol in q.all():
        sol.estado = EstadoSolicitudVacaciones.DISFRUTADO
        n += 1
    db.session.commit()
    return n
