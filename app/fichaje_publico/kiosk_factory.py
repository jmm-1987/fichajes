"""Compatibilidad: reexporta desde rutas.py (un solo módulo para despliegue)."""

from app.fichaje_publico.rutas import (
    ConfigKiosk,
    crear_blueprint_kiosk,
    fichaje_publico_bp,
    fichaje_publico_sfm234r_bp,
)

__all__ = [
    "ConfigKiosk",
    "crear_blueprint_kiosk",
    "fichaje_publico_bp",
    "fichaje_publico_sfm234r_bp",
]
