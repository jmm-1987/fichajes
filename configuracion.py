"""Configuración estática para despliegues sencillos (sin variables de entorno)."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Configuracion:
    """Configuración base de la aplicación."""

    # Clave de sesión / CSRF. Cambiar en despliegues serios.
    SECRET_KEY = "cambiar-en-produccion-clave-larga-y-aleatoria"

    # Base de datos SQLite en el directorio del proyecto.
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(BASE_DIR / "datos" / "fichajes.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    HABILITAR_MODULO_PLANIFICACION = True
    HABILITAR_BLOQUEO_INTENTOS = True
    MAX_INTENTOS_LOGIN = 5
    MINUTOS_BLOQUEO_LOGIN = 15
    HORAS_NOCTURNAS_INICIO = "22:00"
    HORAS_NOCTURNAS_FIN = "06:00"
    FINES_DE_SEMANA_COMO_FESTIVO = False
    TOLERANCIA_FICHAJE_MINUTOS = 5
    JORNADA_TEORICA_HORAS_DIA = 8.0
    # No estamos detrás de proxy inverso en este despliegue sencillo.
    DETRAS_DE_PROXY = False


class ConfiguracionPruebas(Configuracion):
    """Configuración para tests (SQLite en memoria)."""

    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOGIN_DISABLED = False
