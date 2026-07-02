"""Comprueba que los paneles de fichaje público arrancan (ejecutar en el VPS)."""

import sys
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz))

from app import crear_aplicacion

aplicacion = crear_aplicacion()
errores = []

with aplicacion.app_context():
    logos = [
        ("logoalditraex.png", "Alditraex"),
        ("logosfm.png", "SFM"),
    ]
    for nombre, etiqueta in logos:
        ruta = raiz / nombre
        if not ruta.is_file():
            errores.append(f"Falta logo {nombre} ({etiqueta}) en {raiz}")

with aplicacion.test_client() as cliente:
    for path in ("/fichaje-publico/", "/fichaje_publico_sfm234r/"):
        resp = cliente.get(path)
        if resp.status_code != 200:
            errores.append(f"{path} -> HTTP {resp.status_code}")
        else:
            print(f"OK {path} -> {resp.status_code}")

if errores:
    print("ERRORES:")
    for e in errores:
        print(f"  - {e}")
    sys.exit(1)

print("Paneles kiosk verificados correctamente.")
