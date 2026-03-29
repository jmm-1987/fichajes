# Despliegue (instalación individual por cliente)

## VPS Ubuntu 24.04 (producción)

Guía detallada paso a paso: **[MANUAL_DESPLIEGUE_VPS_UBUNTU_24.md](MANUAL_DESPLIEGUE_VPS_UBUNTU_24.md)** (Nginx, Gunicorn, systemd, TLS, SQLite/PostgreSQL).

Archivos de apoyo: `wsgi.py`, `requirements-prod.txt`, `deploy/fichajes.service`, `deploy/nginx-fichajes.conf.example`.

## Requisitos

- Python 3.12
- Entorno virtual recomendado

## Pasos (desarrollo / servidor simple)

1. Clonar o copiar el proyecto en el servidor del cliente.
2. `python -m venv .venv` y activar el entorno.
3. `pip install -r requirements.txt` (en producción también `-r requirements-prod.txt`).
4. Copiar `.env.example` a `.env` y ajustar `SECRET_KEY` y `DATABASE_URL` (por defecto SQLite en `datos/fichajes.db`). Tras proxy inverso con HTTPS, `DETRAS_DE_PROXY=1`.
5. Inicializar base de datos:
   - Opción rápida: `python scripts/inicializar_bd.py`
   - Opción Alembic: `flask db upgrade` (tras generar migraciones).
6. Cargar demo (solo pruebas): `python scripts/cargar_demo.py`
7. Desarrollo: `python ejecutar.py` o `flask run` con `FLASK_APP=ejecutar:aplicacion`
8. Producción: Gunicorn `wsgi:app` (ver manual VPS).

## Producción

- Usar **Gunicorn** (`wsgi:app`) detrás de **Nginx** y **HTTPS**.
- Configurar copias de seguridad periódicas del fichero SQLite o del motor elegido.
- Revisar `docs/NOTAS_LEGALES.md` con el asesor laboral del cliente.
