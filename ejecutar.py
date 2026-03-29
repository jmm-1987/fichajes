"""Punto de entrada para ejecutar la aplicación en desarrollo."""

from app import crear_aplicacion

aplicacion = crear_aplicacion()

if __name__ == "__main__":
    aplicacion.run(debug=True)
