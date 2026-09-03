"""Configuración de la aplicación (con soporte de variables de entorno)."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _get_bool(nombre: str, defecto: bool) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return str(valor).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _get_int(nombre: str, defecto: int) -> int:
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    try:
        return int(str(valor).strip())
    except ValueError:
        return defecto


def _get_float(nombre: str, defecto: float) -> float:
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    try:
        return float(str(valor).strip())
    except ValueError:
        return defecto


class Configuracion:
    """Configuración base de la aplicación."""

    # Clave de sesión / CSRF.
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "cambiar-en-produccion-clave-larga-y-aleatoria",
    )

    # BD por variable de entorno (DATABASE_URL). Si no existe, usa SQLite local.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + str(BASE_DIR / "datos" / "fichajes.db"),
    )
    # Compatibilidad con URL antiguas tipo postgres://
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = _get_bool("WTF_CSRF_ENABLED", True)
    HABILITAR_MODULO_PLANIFICACION = _get_bool("HABILITAR_MODULO_PLANIFICACION", True)
    # Terminal / lector de códigos sin sesión (ruta /fichaje-publico/)
    HABILITAR_FICHAJE_PUBLICO = _get_bool("HABILITAR_FICHAJE_PUBLICO", True)
    # Logo del kiosco /fichaje-publico y de la pantalla de login.
    # En la instancia SFM: KIOSK_LOGO_ARCHIVO=logosfm.png y KIOSK_LOGO_ALT=SFM
    KIOSK_LOGO_ARCHIVO = (
        os.getenv("KIOSK_LOGO_ARCHIVO", "logoalditraex.png").strip()
        or "logoalditraex.png"
    )
    KIOSK_LOGO_ALT = os.getenv("KIOSK_LOGO_ALT", "Alditraex").strip() or "Alditraex"
    HABILITAR_BLOQUEO_INTENTOS = _get_bool("HABILITAR_BLOQUEO_INTENTOS", True)
    MAX_INTENTOS_LOGIN = _get_int("MAX_INTENTOS_LOGIN", 5)
    MINUTOS_BLOQUEO_LOGIN = _get_int("MINUTOS_BLOQUEO_LOGIN", 15)
    # Parámetros laborales por empresa (jornada, nocturnidad, etc.) se gestionan en BD.
    DETRAS_DE_PROXY = _get_bool("DETRAS_DE_PROXY", False)


class ConfiguracionPruebas(Configuracion):
    """Configuración para tests (SQLite en memoria)."""

    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOGIN_DISABLED = False
