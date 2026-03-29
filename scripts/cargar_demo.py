"""Carga datos de demostración (usuarios y registros de ejemplo)."""

import sys
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz))

from app import crear_aplicacion
from app.semillas import cargar_datos_demostracion

aplicacion = crear_aplicacion()

with aplicacion.app_context():
    cargar_datos_demostracion()
    print("Datos demo cargados (si no existían).")
