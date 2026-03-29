"""
Crea tablas con Flask-SQLAlchemy (desarrollo rápido).
Para entornos con Alembic, preferir: flask db upgrade
"""

import sys
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz))

from app import crear_aplicacion
from app.extensiones import db

aplicacion = crear_aplicacion()

with aplicacion.app_context():
    db.create_all()
    print("Tablas creadas (create_all). Use 'flask db migrate' para Alembic.")
