# Manual de despliegue seguro en VPS Ubuntu (producción)

Guía para desplegar **Fichajes** en Ubuntu con foco en seguridad: hardening básico de servidor, PostgreSQL local, Gunicorn + Nginx, TLS y copias de seguridad.

> Alcance: una instalación por cliente (no multi-tenant SaaS).

---

## 1) Arquitectura recomendada

- **App**: Flask (Gunicorn) escuchando en `127.0.0.1:8000` (no expuesto a Internet).
- **Reverse proxy**: Nginx en `80/443` con HTTPS.
- **BD**: PostgreSQL local (`127.0.0.1`), sin exposición pública.
- **Servicio**: `systemd` con usuario de sistema sin shell interactiva.

---

## 2) Requisitos previos

- Ubuntu 24.04 LTS actualizado.
- Dominio apuntando al VPS.
- Acceso SSH con usuario con `sudo`.
- Puertos abiertos en proveedor/VPS: `22`, `80`, `443`.

---

## 3) Hardening inicial del servidor

### 3.1 Actualizar sistema y paquetes base

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  python3.12-venv python3-pip git nginx ufw fail2ban \
  postgresql postgresql-contrib libpq-dev \
  certbot python3-certbot-nginx
```

### 3.2 Usuario de despliegue dedicado

```bash
sudo adduser --disabled-password --gecos "" fichajes
sudo usermod -aG www-data fichajes
sudo mkdir -p /srv/fichajes
sudo chown -R fichajes:fichajes /srv/fichajes
```

### 3.3 SSH seguro (muy recomendado)

Edita `/etc/ssh/sshd_config`:

- `PermitRootLogin no`
- `PasswordAuthentication no` (usar llaves SSH)
- `PubkeyAuthentication yes`
- `X11Forwarding no`

Reinicia SSH:

```bash
sudo systemctl restart ssh
```

> Antes de cerrar sesión, valida que puedes entrar por SSH con llave.

### 3.4 Firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

### 3.5 Fail2ban

```bash
sudo systemctl enable --now fail2ban
sudo systemctl status fail2ban
```

---

## 4) Clonar proyecto y preparar entorno Python

```bash
sudo -u fichajes -H bash -lc '
cd /srv/fichajes
git clone <URL_DEL_REPO> .
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-prod.txt
'
```

---

## 5) Configurar PostgreSQL (seguro)

### 5.1 Crear usuario y base

```bash
sudo -u postgres psql -c "CREATE USER fichajes_app WITH PASSWORD 'MR1037xl@mN.';"
sudo -u postgres psql -c "CREATE DATABASE fichajes OWNER fichajes_app;"
sudo -u postgres psql -c "ALTER ROLE fichajes_app SET client_encoding TO 'UTF8';"
sudo -u postgres psql -c "ALTER ROLE fichajes_app SET timezone TO 'UTC';"
```

### 5.2 Asegurar que PostgreSQL no escucha fuera

En `/etc/postgresql/*/main/postgresql.conf`:
- `listen_addresses = '127.0.0.1'`

En `/etc/postgresql/*/main/pg_hba.conf`, mantener local/loopback (sin aperturas públicas innecesarias).

Reiniciar:

```bash
sudo systemctl restart postgresql
sudo systemctl enable postgresql
```

---

## 6) Variables de entorno de producción

```bash
sudo -u fichajes -H bash -lc '
cd /srv/fichajes
cp .env.example .env
chmod 600 .env
'
```

Edita `/srv/fichajes/.env`:

```env
FLASK_APP=ejecutar:aplicacion
FLASK_DEBUG=0
SECRET_KEY=<GENERA_UNA_MUY_LARGA_Y_ALEATORIA>
DATABASE_URL=postgresql+psycopg2://fichajes_app:CAMBIAR_POR_PASSWORD_LARGA@127.0.0.1:5432/fichajes
DETRAS_DE_PROXY=1
HABILITAR_BLOQUEO_INTENTOS=1
MAX_INTENTOS_LOGIN=5
MINUTOS_BLOQUEO_LOGIN=15
```

Generar `SECRET_KEY`:

```bash
openssl rand -hex 64
```

---

## 7) Migraciones

```bash
sudo -u fichajes -H bash -lc '
cd /srv/fichajes
source .venv/bin/activate
export FLASK_APP=ejecutar:aplicacion
flask db upgrade
'
```

> No cargar datos demo en producción.

---

## 8) Gunicorn con systemd (hardening)

Crea `/etc/systemd/system/fichajes.service`:

```ini
[Unit]
Description=Fichajes Gunicorn
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=fichajes
Group=www-data
WorkingDirectory=/srv/fichajes
EnvironmentFile=/srv/fichajes/.env
ExecStart=/srv/fichajes/.venv/bin/gunicorn --workers 3 --threads 2 --bind 127.0.0.1:8000 wsgi:app
Restart=always
RestartSec=3
TimeoutStopSec=30

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/srv/fichajes
RestrictSUIDSGID=true
LockPersonality=true
MemoryDenyWriteExecute=true

[Install]
WantedBy=multi-user.target
```

Activar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fichajes
sudo systemctl status fichajes
journalctl -u fichajes -f
```

---

## 9) Nginx seguro (HTTPS + cabeceras)

Crea `/etc/nginx/sites-available/fichajes`:

```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
    }
}
```

Habilitar:

```bash
sudo ln -s /etc/nginx/sites-available/fichajes /etc/nginx/sites-enabled/fichajes
sudo nginx -t
sudo systemctl reload nginx
```

### 9.1 Certificado TLS

```bash
sudo certbot --nginx -d tu-dominio.com
sudo certbot renew --dry-run
```

### 9.2 Cabeceras de seguridad (recomendado)

Tras certbot, añade en bloque HTTPS de Nginx:

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(self)" always;
```

> Si usas integraciones externas, ajusta CSP cuidadosamente antes de forzarla.

---

## 10) Backups y recuperación (obligatorio)

### 10.1 Script de backup PostgreSQL

Crea `/usr/local/bin/backup_fichajes.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
export PGPASSWORD='CAMBIAR_POR_PASSWORD_LARGA'
DEST=/var/backups/fichajes
mkdir -p "$DEST"
FILE="$DEST/fichajes_$(date +%F_%H%M).sql.gz"
pg_dump -h 127.0.0.1 -U fichajes_app fichajes | gzip > "$FILE"
find "$DEST" -type f -name "fichajes_*.sql.gz" -mtime +14 -delete
```

```bash
sudo chmod 700 /usr/local/bin/backup_fichajes.sh
```

### 10.2 Programar con cron (diario)

```bash
sudo crontab -e
```

Añadir:

```cron
15 3 * * * /usr/local/bin/backup_fichajes.sh
```

### 10.3 Probar restauración (muy importante)

Al menos 1 vez al mes, restaurar en una BD de prueba y validar login + informes.

---

## 11) Operación y actualizaciones seguras

```bash
sudo systemctl stop fichajes
sudo -u fichajes -H bash -lc '
cd /srv/fichajes
source .venv/bin/activate
git pull
pip install -r requirements.txt -r requirements-prod.txt
export FLASK_APP=ejecutar:aplicacion
flask db upgrade
'
sudo systemctl start fichajes
sudo systemctl status fichajes
```

---

## 12) Checklist de seguridad antes de abrir producción

- [ ] `FLASK_DEBUG=0`
- [ ] `SECRET_KEY` robusta y única
- [ ] PostgreSQL en `127.0.0.1` (no público)
- [ ] UFW activo con mínimo de puertos
- [ ] `PermitRootLogin no` y SSH con llaves
- [ ] HTTPS activo y renovación automática OK
- [ ] Backups automáticos + prueba de restauración
- [ ] Servicio systemd con hardening y reinicio automático
- [ ] Revisión de logs (`journalctl`, Nginx, fail2ban)

---

## 13) Notas legales y protección de datos

- Definir política de retención conforme a obligaciones laborales.
- Restringir acceso por roles (principio de mínimo privilegio).
- Documentar backups, restauración y trazabilidad.
- Revisar `docs/NOTAS_LEGALES.md` con asesoría laboral y de protección de datos.

