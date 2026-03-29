# Manual de despliegue en VPS (Ubuntu 24.04 LTS)

Guía para publicar la aplicación de **control horario** (Flask) en un servidor con **Ubuntu 24.04**, **Nginx**, **Gunicorn** y opcionalmente **PostgreSQL**. Rutas de ejemplo: instalación en `/srv/fichajes` y usuario de sistema `fichajes`.

## 1. Resumen de arquitectura

| Componente | Función |
|------------|---------|
| **Gunicorn** | Servidor WSGI; escucha en `127.0.0.1:8000` |
| **Nginx** | Proxy inverso, TLS (HTTPS), cabeceras `X-Forwarded-*` |
| **systemd** | Arranque automático y reinicio del servicio |
| **SQLite o PostgreSQL** | Base de datos (`DATABASE_URL`) |

En el repositorio: `wsgi.py`, `requirements-prod.txt`, `deploy/fichajes.service`, `deploy/nginx-fichajes.conf.example`.

## 2. Requisitos

- Ubuntu **24.04 LTS** actualizado
- Acceso **SSH** con `sudo`
- **Dominio** apuntando al VPS (recomendado para HTTPS)
- Python **3.12** (incluido en 24.04)

## 3. Paquetes del sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.12-venv python3-pip git nginx
```

PostgreSQL (opcional):

```bash
sudo apt install -y postgresql postgresql-contrib libpq-dev
```

## 4. Usuario y código

```bash
sudo useradd --system --home /srv/fichajes --create-home --shell /bin/bash fichajes
sudo mkdir -p /srv/fichajes/datos
sudo chown -R fichajes:fichajes /srv/fichajes
```

Copie el proyecto bajo `/srv/fichajes` (por ejemplo `sudo -u fichajes git clone <URL> .` desde `/srv/fichajes`).

## 5. Entorno virtual

```bash
sudo -u fichajes -i
cd /srv/fichajes
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-prod.txt
```

## 6. Variables de entorno

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

Imprescindible en producción:

- **`SECRET_KEY`**: `openssl rand -hex 32`
- **`DATABASE_URL`**: ver apartados SQLite o PostgreSQL
- **`DETRAS_DE_PROXY=1`** cuando Nginx termine HTTPS delante de la app
- No activar **`FLASK_DEBUG`** en producción

SQLite con ruta absoluta en Linux (cuatro barras tras `sqlite:`):

```env
DATABASE_URL=sqlite:////srv/fichajes/datos/fichajes.db
```

PostgreSQL:

```bash
sudo -u postgres psql -c "CREATE USER fichajes_app WITH PASSWORD 'clave_segura';"
sudo -u postgres psql -c "CREATE DATABASE fichajes OWNER fichajes_app;"
```

```env
DATABASE_URL=postgresql+psycopg2://fichajes_app:clave_segura@127.0.0.1:5432/fichajes
```

## 7. Migraciones

```bash
cd /srv/fichajes
source .venv/bin/activate
export FLASK_APP=ejecutar:aplicacion
flask db upgrade
```

No ejecute `scripts/cargar_demo.py` en producción con datos reales.

## 8. Prueba manual de Gunicorn

```bash
gunicorn --bind 127.0.0.1:8000 wsgi:app
```

`curl -I http://127.0.0.1:8000/` y luego Ctrl+C.

## 9. systemd

```bash
sudo cp /srv/fichajes/deploy/fichajes.service /etc/systemd/system/fichajes.service
sudo nano /etc/systemd/system/fichajes.service
sudo systemctl daemon-reload
sudo systemctl enable --now fichajes
sudo systemctl status fichajes
journalctl -u fichajes -f
```

## 10. Nginx

```bash
sudo cp /srv/fichajes/deploy/nginx-fichajes.conf.example /etc/nginx/sites-available/fichajes
sudo nano /etc/nginx/sites-available/fichajes
sudo ln -sf /etc/nginx/sites-available/fichajes /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Edite `server_name` con su dominio.

## 11. HTTPS (Certbot)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d su-dominio.ejemplo
sudo certbot renew --dry-run
```

## 12. Cortafuegos UFW

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## 13. Actualizar la aplicación

```bash
sudo systemctl stop fichajes
sudo -u fichajes -i
cd /srv/fichajes && source .venv/bin/activate
git pull
pip install -r requirements.txt -r requirements-prod.txt
export FLASK_APP=ejecutar:aplicacion
flask db upgrade
exit
sudo systemctl start fichajes
```

## 14. Copias de seguridad

- **SQLite**: copiar `datos/*.db` de forma periódica.
- **PostgreSQL**: `pg_dump -U fichajes_app -h 127.0.0.1 fichajes > backup.sql`

## 15. Problemas frecuentes

| Síntoma | Qué revisar |
|---------|-------------|
| 502 | `systemctl status fichajes`, `journalctl -u fichajes` |
| IP del proxy en logs | `DETRAS_DE_PROXY=1` y cabeceras del ejemplo Nginx |
| SQLite locked / permisos | Propietario `fichajes` en `datos/` |

Más detalle en `docs/NOTAS_LEGALES.md` y `.env.example`.
