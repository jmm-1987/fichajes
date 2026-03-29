# Control horario — aplicación web (Flask)

Aplicación para **registro horario** de personas trabajadoras en instalaciones individuales por empresa (España). Incluye portal empleado (móvil), administración, vacaciones, informes, auditoría y módulo opcional de planificación semanal.

## Stack

- Python 3.12, Flask, SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF
- SQLite por defecto (configurable por `DATABASE_URL`)
- Bootstrap 5 (CDN), HTMX, Alpine.js, CSS propio
- Tests con pytest

## Arranque rápido

```powershell
cd c:\ruta\al\proyecto
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python scripts\inicializar_bd.py
python scripts\cargar_demo.py
python ejecutar.py
```

Abrir `http://127.0.0.1:5000` e iniciar sesión con cuentas demo (tras `cargar_demo.py`). El acceso es por **nombre de usuario** (sin arrobas); se guarda en base de datos en el campo `correo_electronico` por compatibilidad histórica.

| Rol | Usuario | Contraseña |
|-----|---------|------------|
| Superadministrador | `superadmin` | Demo1234! |
| Mánager / responsable | `manager` | Demo1234! |
| Empleado | `empleado` | Demo1234! |

Si ya tenía datos antiguos con correos `@demo.local`, borre la base SQLite (`datos/fichajes.db`) y vuelva a ejecutar `scripts/inicializar_bd.py` y `scripts/cargar_demo.py`.

## Migraciones (Alembic / Flask-Migrate)

```powershell
$env:FLASK_APP = "ejecutar:aplicacion"
flask db init
flask db migrate -m "inicial"
flask db upgrade
```

Si ya usó `scripts/inicializar_bd.py`, puede eliminar la BD y volver a crear con migraciones para alinear versiones.

## Despliegue en VPS (Ubuntu 24.04)

Manual completo: [docs/MANUAL_DESPLIEGUE_VPS_UBUNTU_24.md](docs/MANUAL_DESPLIEGUE_VPS_UBUNTU_24.md) (Nginx, Gunicorn, systemd, Let’s Encrypt, SQLite o PostgreSQL).

Guía **paso a paso con todos los comandos**, usuario **root** y dominio **fichajes.jm2-tech.es**: [docs/DESPLIEGUE_PASO_A_PASO_ROOT_JM2.md](docs/DESPLIEGUE_PASO_A_PASO_ROOT_JM2.md).

## Estructura principal

- `app/modelos/` — ORM (`Empleado`, `RegistroJornada`, `RegistroAuditoria`, etc.)
- `app/fichajes/` — fichajes, cálculos, validación, geolocalización en el momento del fichaje
- `app/auditoria/` — servicio de registro inmutable
- `app/informes/` — filtros y exportación CSV / Excel / PDF
- `app/planificacion/` — blueprint desactivable
- `docs/` — legal, planificación y despliegue

## Tests

```powershell
pytest
```

## Licencia

Uso interno del cliente; ajustar según necesidad.
