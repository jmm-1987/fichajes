"""Carga de configuración desde variables de entorno."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Configuracion:
    """Configuración base de la aplicación."""

    SECRET_KEY = os.environ.get("SECRET_KEY") or "desarrollo-cambiar"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + str(BASE_DIR / "datos" / "fichajes.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    HABILITAR_MODULO_PLANIFICACION = (
        os.environ.get("HABILITAR_MODULO_PLANIFICACION", "1") == "1"
    )
    HABILITAR_BLOQUEO_INTENTOS = (
        os.environ.get("HABILITAR_BLOQUEO_INTENTOS", "0") == "1"
    )
    MAX_INTENTOS_LOGIN = int(os.environ.get("MAX_INTENTOS_LOGIN", "5"))
    MINUTOS_BLOQUEO_LOGIN = int(os.environ.get("MINUTOS_BLOQUEO_LOGIN", "15"))
    HORAS_NOCTURNAS_INICIO = os.environ.get("HORAS_NOCTURNAS_INICIO", "22:00")
    HORAS_NOCTURNAS_FIN = os.environ.get("HORAS_NOCTURNAS_FIN", "06:00")
    FINES_DE_SEMANA_COMO_FESTIVO = (
        os.environ.get("FINES_DE_SEMANA_COMO_FESTIVO", "0") == "1"
    )
    TOLERANCIA_FICHAJE_MINUTOS = int(
        os.environ.get("TOLERANCIA_FICHAJE_MINUTOS", "5")
    )
    JORNADA_TEORICA_HORAS_DIA = float(
        os.environ.get("JORNADA_TEORICA_HORAS_DIA", "8")
    )
    # Tras Nginx/Apache como proxy inverso (HTTPS, IP real del cliente).
    DETRAS_DE_PROXY = os.environ.get("DETRAS_DE_PROXY", "0") == "1"


class ConfiguracionPruebas(Configuracion):
    """Configuración para tests (SQLite en memoria)."""

    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOGIN_DISABLED = False
