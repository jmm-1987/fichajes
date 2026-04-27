# Guía PostgreSQL (producción recomendada)

Esta guía deja la aplicación lista para usar PostgreSQL en VPS Ubuntu.

## 1) Instalar PostgreSQL

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib libpq-dev
```

## 2) Crear usuario y base de datos

```bash
sudo -u postgres psql -c "CREATE USER fichajes_app WITH PASSWORD 'CAMBIAR_CLAVE_SEGURA';"
sudo -u postgres psql -c "CREATE DATABASE fichajes OWNER fichajes_app;"
```

Opcional (más robusto en producción):

```bash
sudo -u postgres psql -c "ALTER ROLE fichajes_app SET client_encoding TO 'UTF8';"
sudo -u postgres psql -c "ALTER ROLE fichajes_app SET timezone TO 'UTC';"
```

## 3) Configurar `.env`

En el proyecto:

```env
DATABASE_URL=postgresql+psycopg2://fichajes_app:CAMBIAR_CLAVE_SEGURA@127.0.0.1:5432/fichajes
DETRAS_DE_PROXY=1
```

También asegure `SECRET_KEY` fuerte en producción.

## 4) Instalar dependencias Python

```bash
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-prod.txt
```

## 5) Crear esquema con migraciones

```bash
export FLASK_APP=ejecutar:aplicacion
flask db upgrade
```

## 6) Migrar datos desde SQLite (si ya hay histórico)

Si parte de SQLite y quiere mantener datos:

1. Haga copia de seguridad del SQLite actual.
2. Exporte tablas relevantes y cárguelas en PostgreSQL (script ETL o volcado controlado).
3. Valide conteos por tabla y muestreo funcional (fichajes, auditoría, solicitudes).

Notas:
- No hay migración automática universal SQLite->PostgreSQL sin revisar tipos/fechas.
- En proyectos con histórico legal, valide especialmente `registros_jornada` y `registros_auditoria`.

## 7) Verificación rápida

```bash
python -c "from app import crear_aplicacion; app=crear_aplicacion(); print(app.config['SQLALCHEMY_DATABASE_URI'])"
```

Debe mostrar URL PostgreSQL.

Luego:

```bash
gunicorn --bind 127.0.0.1:8000 wsgi:app
```

Y probar login + fichaje + informe.

## 8) Copias de seguridad

Backup SQL diario:

```bash
pg_dump -U fichajes_app -h 127.0.0.1 fichajes > /ruta/backup_$(date +%F).sql
```

Recomendado: rotación + prueba periódica de restauración.
