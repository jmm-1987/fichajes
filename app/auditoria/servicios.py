"""Servicio central de registro inmutable de auditoría."""

import json
from typing import Any, Optional

from flask import has_request_context, request
from flask_login import current_user

from app.extensiones import db
from app.modelos import RegistroAuditoria
from app.utilidades.fechas import formatear_fecha_hora


def registrar_auditoria(
    tipo_entidad: str,
    id_entidad: int,
    accion: str,
    estado_anterior: Optional[Any] = None,
    estado_nuevo: Optional[Any] = None,
    motivo: Optional[str] = None,
    usuario_actor_id: Optional[int] = None,
    rol_actor: Optional[str] = None,
    origen_cambio: Optional[str] = None,
) -> RegistroAuditoria:
    """
    Inserta un registro de auditoría. No actualiza ni borra filas existentes.
    """
    if usuario_actor_id is None and has_request_context() and current_user is not None:
        try:
            aut = bool(current_user.is_authenticated)
        except AttributeError:
            aut = False
        if aut:
            usuario_actor_id = current_user.id
            rol_actor = rol_actor or current_user.rol

    ip = request.remote_addr if request else None
    ua = request.headers.get("User-Agent", "")[:512] if request else None

    registro = RegistroAuditoria(
        tipo_entidad=tipo_entidad,
        id_entidad=id_entidad,
        accion=accion,
        usuario_actor_id=usuario_actor_id,
        rol_actor=rol_actor,
        motivo=motivo,
        estado_anterior_json=_a_json(estado_anterior),
        estado_nuevo_json=_a_json(estado_nuevo),
        direccion_ip=ip,
        agente_usuario=ua,
        origen_cambio=origen_cambio or "web",
    )
    db.session.add(registro)
    db.session.flush()
    return registro


def _a_json(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    if isinstance(valor, str):
        return valor
    try:
        return json.dumps(valor, ensure_ascii=False, default=str)
    except TypeError:
        return str(valor)


def serializar_registro_jornada(registro) -> dict:
    """Representación dict de un RegistroJornada para auditoría."""
    return {
        "id": registro.id,
        "empleado_id": registro.empleado_id,
        "tipo_registro": registro.tipo_registro,
        "fecha_hora_servidor": formatear_fecha_hora(registro.fecha_hora_servidor)
        if registro.fecha_hora_servidor
        else None,
        "fecha_hora_cliente": formatear_fecha_hora(registro.fecha_hora_cliente)
        if registro.fecha_hora_cliente
        else None,
        "estado": registro.estado,
        "origen": registro.origen,
        "notas": registro.notas,
    }
