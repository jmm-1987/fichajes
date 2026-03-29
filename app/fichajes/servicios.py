"""Registro y corrección de fichajes con auditoría."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from flask import request
from app.auditoria.servicios import registrar_auditoria, serializar_registro_jornada
from app.constantes import (
    EstadoRegistroJornada,
    OrigenRegistroJornada,
    TipoAccionAuditoria,
    TipoRegistroJornada,
)
from app.extensiones import db
from app.fichajes.geolocalizacion import texto_ubicacion_humano
from app.fichajes.validadores import (
    ahora_servidor,
    filtrar_registros_validos,
    validar_nuevo_tipo,
)
from app.modelos import RegistroJornada, SolicitudCorreccion


def obtener_registros_dia_ordenados(empleado_id: int, dia: date) -> list[RegistroJornada]:
    inicio = datetime.combine(dia, time.min, tzinfo=timezone.utc)
    fin = inicio + timedelta(days=1)
    regs = (
        RegistroJornada.query.filter(
            RegistroJornada.empleado_id == empleado_id,
            RegistroJornada.fecha_hora_servidor >= inicio,
            RegistroJornada.fecha_hora_servidor < fin,
        )
        .order_by(RegistroJornada.fecha_hora_servidor)
        .all()
    )
    return filtrar_registros_validos(regs)


def datos_contador_portal_fichaje(registros: list) -> dict:
    """
    Estado para el contador en vivo del portal de fichaje.
    Cuenta el tiempo desde la última apertura de tramo: entrada, o fin de pausa
    si hubo pausa; se cierra con salida. Solo corre mientras la jornada está activa.
    """
    inicio_tramo: datetime | None = None
    for r in registros:
        t = r.tipo_registro
        if t == TipoRegistroJornada.ENTRADA:
            inicio_tramo = r.fecha_hora_servidor
        elif t == TipoRegistroJornada.SALIDA:
            inicio_tramo = None
        elif t == TipoRegistroJornada.PAUSA_FIN:
            inicio_tramo = r.fecha_hora_servidor

    if not registros:
        return {
            "mostrar_contador": False,
            "contador_inicio_iso": None,
            "en_pausa": False,
        }

    ultimo = registros[-1].tipo_registro
    jornada_activa = ultimo in (
        TipoRegistroJornada.ENTRADA,
        TipoRegistroJornada.PAUSA_FIN,
    )
    en_pausa = ultimo == TipoRegistroJornada.PAUSA_INICIO

    hay_jornada_abierta_hoy = inicio_tramo is not None

    inicio_iso: str | None = None
    if inicio_tramo is not None and jornada_activa:
        ts = inicio_tramo
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ts = ts.astimezone(timezone.utc)
        inicio_iso = ts.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    return {
        "mostrar_contador": bool(inicio_iso),
        "contador_inicio_iso": inicio_iso,
        "en_pausa": bool(hay_jornada_abierta_hoy and en_pausa),
    }


def registrar_marca(
    empleado_id: int,
    tipo_registro: str,
    usuario_id: Optional[int],
    origen: str = OrigenRegistroJornada.WEB_EMPLEADO,
    latitud: Optional[float] = None,
    longitud: Optional[float] = None,
    precision_metros: Optional[float] = None,
    fecha_hora_cliente: Optional[datetime] = None,
    notas: Optional[str] = None,
    validar_secuencia: bool = True,
) -> tuple[RegistroJornada | None, Optional[str]]:
    """
    Crea un fichaje. Devuelve (registro, error).
    """
    dia = ahora_servidor().date()
    existentes = obtener_registros_dia_ordenados(empleado_id, dia)
    if validar_secuencia:
        ok, msg = validar_nuevo_tipo(existentes, tipo_registro)
        if not ok:
            return None, msg

    ip = request.remote_addr if request else None
    ua = request.headers.get("User-Agent", "")[:512] if request else None
    prec = float(precision_metros) if precision_metros is not None else None
    txt_ub = texto_ubicacion_humano(latitud, longitud, prec)

    reg = RegistroJornada(
        empleado_id=empleado_id,
        tipo_registro=tipo_registro,
        fecha_hora_servidor=ahora_servidor(),
        fecha_hora_cliente=fecha_hora_cliente,
        latitud=Decimal(str(latitud)) if latitud is not None else None,
        longitud=Decimal(str(longitud)) if longitud is not None else None,
        precision_metros=Decimal(str(precision_metros))
        if precision_metros is not None
        else None,
        texto_ubicacion=txt_ub[:500],
        direccion_ip=ip,
        agente_usuario=ua,
        origen=origen,
        estado=EstadoRegistroJornada.VALIDO,
        notas=notas,
        creado_por_usuario_id=usuario_id,
    )
    db.session.add(reg)
    db.session.flush()
    registrar_auditoria(
        tipo_entidad="registro_jornada",
        id_entidad=reg.id,
        accion=TipoAccionAuditoria.CREAR,
        estado_anterior=None,
        estado_nuevo=serializar_registro_jornada(reg),
        motivo="Fichaje registrado",
        usuario_actor_id=usuario_id,
        origen_cambio=origen,
    )
    db.session.commit()
    return reg, None


def corregir_registro_admin(
    registro_id: int,
    usuario_actor_id: int,
    rol_actor: str,
    campos: dict[str, Any],
    motivo: str,
) -> tuple[bool, Optional[str]]:
    """
    Modifica campos permitidos de un fichaje con motivo obligatorio e auditoría.
    No elimina el registro.
    """
    if not motivo or not motivo.strip():
        return False, "El motivo es obligatorio."

    reg = RegistroJornada.query.get(registro_id)
    if not reg:
        return False, "Registro no encontrado."

    antes = serializar_registro_jornada(reg)
    permitidos = {
        "fecha_hora_servidor",
        "fecha_hora_cliente",
        "tipo_registro",
        "estado",
        "notas",
    }
    for clave, valor in campos.items():
        if clave in permitidos and hasattr(reg, clave):
            setattr(reg, clave, valor)

    if "estado" not in campos:
        reg.estado = EstadoRegistroJornada.CORREGIDO
    despues = serializar_registro_jornada(reg)

    registrar_auditoria(
        tipo_entidad="registro_jornada",
        id_entidad=reg.id,
        accion=TipoAccionAuditoria.ACTUALIZAR,
        estado_anterior=antes,
        estado_nuevo=despues,
        motivo=motivo.strip(),
        usuario_actor_id=usuario_actor_id,
        rol_actor=rol_actor,
        origen_cambio=OrigenRegistroJornada.ADMIN,
    )
    db.session.commit()
    return True, None


def anular_registro_admin(
    registro_id: int,
    usuario_actor_id: int,
    rol_actor: str,
    motivo: str,
) -> tuple[bool, Optional[str]]:
    """Marca fichaje como anulado con trazabilidad."""
    return corregir_registro_admin(
        registro_id,
        usuario_actor_id,
        rol_actor,
        {"estado": EstadoRegistroJornada.ANULADO},
        motivo,
    )


def crear_solicitud_correccion_empleado(
    empleado_id: int,
    registro_jornada_id: Optional[int],
    motivo: str,
    valor_solicitado: Optional[str] = None,
    valor_actual: Optional[str] = None,
) -> SolicitudCorreccion:
    """El empleado solicita revisión de un fichaje o jornada."""
    sol = SolicitudCorreccion(
        empleado_id=empleado_id,
        registro_jornada_id=registro_jornada_id,
        tipo_solicitud="correccion_horario",
        valor_solicitado=valor_solicitado,
        valor_actual=valor_actual,
        motivo=motivo,
        estado="pendiente",
    )
    db.session.add(sol)
    db.session.flush()
    registrar_auditoria(
        tipo_entidad="solicitud_correccion",
        id_entidad=sol.id,
        accion=TipoAccionAuditoria.CREAR,
        estado_nuevo={
            "empleado_id": empleado_id,
            "registro_jornada_id": registro_jornada_id,
            "motivo": motivo,
        },
        motivo="Solicitud creada por empleado",
        origen_cambio="web_empleado",
    )
    db.session.commit()
    return sol


def resolver_solicitud_correccion(
    solicitud_id: int,
    aprobar: bool,
    usuario_revisor_id: int,
    notas: Optional[str] = None,
) -> tuple[bool, str]:
    """RRHH aprueba o rechaza la solicitud."""
    sol = SolicitudCorreccion.query.get(solicitud_id)
    if not sol or sol.estado != "pendiente":
        return False, "Solicitud no válida."

    sol.estado = "aprobada" if aprobar else "rechazada"
    sol.revisado_por_usuario_id = usuario_revisor_id
    sol.revisado_en = ahora_servidor()
    sol.notas_resolucion = notas

    accion = (
        TipoAccionAuditoria.APROBAR if aprobar else TipoAccionAuditoria.RECHAZAR
    )
    registrar_auditoria(
        tipo_entidad="solicitud_correccion",
        id_entidad=sol.id,
        accion=accion,
        estado_nuevo={"estado": sol.estado, "notas": notas},
        motivo=notas or "Resolución de solicitud",
        usuario_actor_id=usuario_revisor_id,
        origen_cambio="admin",
    )
    db.session.commit()
    return True, "Actualizado."
