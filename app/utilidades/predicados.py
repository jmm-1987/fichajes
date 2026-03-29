"""Decoradores y comprobaciones de permisos por rol."""

from functools import wraps
from typing import Callable, Iterable

from flask import abort, current_app
from flask_login import current_user

from app.constantes import RolUsuario


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
    if current_user.rol in (
        RolUsuario.SUPERADMINISTRADOR,
        RolUsuario.ADMINISTRADOR_EMPRESA,
    ):
        return True
    empleado_actual = getattr(current_user, "empleado", None)
    if not empleado_actual:
        return False
    if current_user.rol == RolUsuario.EMPLEADO:
        return empleado_actual.id == empleado_id
    if current_user.rol == RolUsuario.RESPONSABLE:
        from app.modelos import Empleado

        subordinado = Empleado.query.filter_by(id=empleado_id).first()
        if not subordinado:
            return False
        return subordinado.responsable_id == empleado_actual.id
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
