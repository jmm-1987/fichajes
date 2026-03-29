"""Lógica de negocio de autenticación y bloqueo por intentos."""

import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensiones import db
from app.modelos import Usuario


def ahora_utc():
    return datetime.now(timezone.utc)


def autenticar_usuario(nombre_usuario: str, contrasena: str) -> Usuario | None:
    """
    Valida credenciales y devuelve el usuario o None.
    El identificador se guarda en `correo_electronico` (nombre histórico de columna).
    """
    clave = (nombre_usuario or "").strip().lower()
    usuario = Usuario.query.filter_by(correo_electronico=clave).first()
    if not usuario or not usuario.activo:
        return None

    cfg = current_app.config
    if cfg.get("HABILITAR_BLOQUEO_INTENTOS"):
        if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora_utc():
            return None
        if usuario.bloqueado_hasta and usuario.bloqueado_hasta <= ahora_utc():
            usuario.bloqueado_hasta = None
            usuario.intentos_fallidos_login = 0

    if not usuario.verificar_contrasena(contrasena):
        if cfg.get("HABILITAR_BLOQUEO_INTENTOS"):
            usuario.intentos_fallidos_login = (usuario.intentos_fallidos_login or 0) + 1
            max_i = cfg.get("MAX_INTENTOS_LOGIN", 5)
            if usuario.intentos_fallidos_login >= max_i:
                minutos = cfg.get("MINUTOS_BLOQUEO_LOGIN", 15)
                usuario.bloqueado_hasta = ahora_utc() + timedelta(minutes=minutos)
            db.session.commit()
        return None

    usuario.intentos_fallidos_login = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = ahora_utc()
    db.session.commit()
    return usuario


def crear_token_recuperacion(usuario: Usuario, horas_validez: int = 24) -> str:
    """Genera token opaco y fecha de caducidad."""
    token = secrets.token_urlsafe(32)
    usuario.token_recuperacion = token
    usuario.expira_token_recuperacion = ahora_utc() + timedelta(hours=horas_validez)
    db.session.commit()
    return token


def buscar_usuario_por_token_recuperacion(token: str) -> Usuario | None:
    """Usuario con token válido y no caducado."""
    if not token:
        return None
    u = Usuario.query.filter_by(token_recuperacion=token).first()
    if not u or not u.expira_token_recuperacion:
        return None
    if u.expira_token_recuperacion < ahora_utc():
        return None
    return u


def restablecer_contrasena_con_token(usuario: Usuario, nueva: str) -> None:
    """Asigna nueva contraseña e invalida el token."""
    usuario.establecer_contrasena(nueva)
    usuario.token_recuperacion = None
    usuario.expira_token_recuperacion = None
    usuario.intentos_fallidos_login = 0
    db.session.commit()
