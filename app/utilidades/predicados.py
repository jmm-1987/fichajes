"""Decoradores y comprobaciones de permisos por rol."""

from functools import wraps
from typing import Callable, Iterable

from flask import abort, current_app
from flask_login import current_user

from app.constantes import RolUsuario
from app.modelos import Empleado, Usuario


def roles_permitidos(*roles: str) -> Callable:
    """
    Restringe la vista a usuarios autenticados con uno de los roles indicados.
    """

    def decorador(vista: Callable) -> Callable:
        @wraps(vista)
        def envoltorio(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if current_user.rol not in roles:
                abort(403)
            return vista(*args, **kwargs)

        return envoltorio

    return decorador


def es_superadministrador() -> bool:
    """True si el usuario actual es superadministrador."""
    return (
        current_user.is_authenticated
        and current_user.rol == RolUsuario.SUPERADMINISTRADOR
    )


def es_administrador_o_superior() -> bool:
    """Admin empresa o superadmin."""
    return current_user.is_authenticated and current_user.rol in (
        RolUsuario.SUPERADMINISTRADOR,
        RolUsuario.ADMINISTRADOR_EMPRESA,
    )


def es_responsable_o_superior() -> bool:
    """Responsable, admin o superadmin."""
    return current_user.is_authenticated and current_user.rol in (
        RolUsuario.SUPERADMINISTRADOR,
        RolUsuario.ADMINISTRADOR_EMPRESA,
        RolUsuario.RESPONSABLE,
    )


def puede_gestionar_empleado(empleado_id: int) -> bool:
    """
    Determina si el usuario puede ver/editar datos del empleado dado.
    Superadmin y RRHH: sí. Responsable: solo su equipo. Empleado: solo él mismo.
    """
    if not current_user.is_authenticated:
        return False
    empleado_obj = Empleado.query.filter_by(id=empleado_id).first()
    if not empleado_obj:
        return False

    # Superadmin puede gestionar cualquier empleado, independientemente de empresa.
    if current_user.rol == RolUsuario.SUPERADMINISTRADOR:
        return True

    # Resto de roles solo dentro de su misma empresa.
    empleado_actual = getattr(current_user, "empleado", None)
    empresa_usuario = getattr(current_user, "empresa_id", None)
    empresa_obj = empleado_obj.empresa_id

    if current_user.rol == RolUsuario.ADMINISTRADOR_EMPRESA:
        # Admin empresa: por empresa (desde empleado o empresa_id en usuario)
        if empresa_usuario is not None:
            return empresa_usuario == empresa_obj
        if empleado_actual:
            return empleado_actual.empresa_id == empresa_obj
        return False

    if current_user.rol == RolUsuario.EMPLEADO:
        return empleado_actual is not None and empleado_actual.id == empleado_id

    if current_user.rol == RolUsuario.RESPONSABLE:
        # Manager: puede gestionar empleados de su empresa cuyo responsable_usuario_id sea su usuario
        if empresa_usuario is not None and empresa_usuario != empresa_obj:
            return False
        if empleado_obj.responsable_usuario_id is not None:
            return empleado_obj.responsable_usuario_id == current_user.id
        # Compatibilidad antigua: caer al comportamiento previo si no hay responsable_usuario_id
        if empleado_actual:
            return empleado_obj.responsable_id == empleado_actual.id
    return False


def obtener_id_empleado_actual() -> int | None:
    """ID del empleado vinculado al usuario logueado, o None."""
    if not current_user.is_authenticated:
        return None
    emp = getattr(current_user, "empleado", None)
    return emp.id if emp else None


def roles_dashboard_admin() -> Iterable[str]:
    """Roles que ven el panel de administración."""
    return (
        RolUsuario.SUPERADMINISTRADOR,
        RolUsuario.ADMINISTRADOR_EMPRESA,
        RolUsuario.RESPONSABLE,
    )


def modulo_planificacion_habilitado() -> bool:
    """Lee la bandera de funcionalidad del planificador."""
    return bool(current_app.config.get("HABILITAR_MODULO_PLANIFICACION", True))
