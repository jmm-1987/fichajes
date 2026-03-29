# Despliegue completo: Ubuntu 24.04, usuario root, dominio fichajes.jm2-tech.es

Manual **de principio a fin** para publicar la aplicación de control horario en un VPS.  
**Usuario del sistema:** `root` (todo se ejecuta como root salvo que se indique lo contrario).  
**Dominio:** `fichajes.jm2-tech.es`  
**Ruta de la aplicación:** `/root/fichajes`

> **Nota de seguridad:** En producción es más recomendable un usuario sin privilegios (p. ej. `fichajes`) y servicios sin `User=root`. Si usa root, proteja el SSH con clave fuerte o solo-clave y mantenga el sistema actualizado.

---

## 0. Antes de empezar

1. **VPS con Ubuntu 24.04 LTS** y acceso SSH como `root`.
2. **DNS:** un registro **A** (o AAAA si solo IPv6) para el host:
   - **Nombre:** `fichajes` (o `fichajes.jm2-tech.es` según su proveedor).
   - **Valor:** la IP pública del VPS.
3. Comprobar que resuelve (desde su PC, tras propagar DNS):

```bash
ping -c 2 fichajes.jm2-tech.es
```

---

## 1. Conectar al servidor

```bash
ssh root@SU_IP_DEL_VPS
```

Sustituya `SU_IP_DEL_VPS` por la IP o por `fichajes.jm2-tech.es` si ya apunta al servidor.

---

## 2. Actualizar el sistema e instalar paquetes

```bash
apt update && apt upgrade -y
apt install -y python3.12-venv python3-pip git nginx curl
```

Opcional — **solo si usará PostgreSQL** en lugar de SQLite:

```bash
apt install -y postgresql postgresql-contrib libpq-dev
```

---

## 3. Colocar el código en `/root/fichajes`

### Opción A — con Git

```bash
cd /root
git clone URL_DE_SU_REPOSITORIO fichajes
cd fichajes
```

### Opción B — subir un ZIP

Suba el proyecto con `scp` desde su PC (ejemplo):

```bash
# En su PC (no en el VPS)
scp -r ./fichajes root@fichajes.jm2-tech.es:/root/
```

En el VPS:

```bash
cd /root/fichajes
```

Asegúrese de que existen `wsgi.py`, `ejecutar.py`, `app/`, `configuracion.py`, `migrations/`, etc.

---

## 4. Directorio de datos (SQLite)

```bash
mkdir -p /root/fichajes/datos
```

---

## 5. Entorno virtual Python e instalación de dependencias

```bash
cd /root/fichajes
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-prod.txt
```

---

## 6. Fichero `.env`

```bash
cd /root/fichajes
cp .env.example .env
nano .env
```

Contenido recomendado para **este dominio y HTTPS detrás de Nginx** (ajuste `SECRET_KEY` y, si aplica, la base de datos):

```env
FLASK_APP=ejecutar:aplicacion
SECRET_KEY=PONGA_AQUI_UNA_CLAVE_LARGA_GENERADA
DATABASE_URL=sqlite:////root/fichajes/datos/fichajes.db
DETRAS_DE_PROXY=1
HABILITAR_MODULO_PLANIFICACION=1
HABILITAR_BLOQUEO_INTENTOS=1
MAX_INTENTOS_LOGIN=5
MINUTOS_BLOQUEO_LOGIN=15
HORAS_NOCTURNAS_INICIO=22:00
HORAS_NOCTURNAS_FIN=06:00
FINES_DE_SEMANA_COMO_FESTIVO=0
TOLERANCIA_FICHAJE_MINUTOS=5
JORNADA_TEORICA_HORAS_DIA=8
```

- **No** incluya `FLASK_DEBUG=1` en producción.
- Genere `SECRET_KEY`:

```bash
openssl rand -hex 32
```

Pegue el resultado en `.env` como valor de `SECRET_KEY`.

Permisos del `.env`:

```bash
chmod 600 /root/fichajes/.env
```

---

## 7. Crear tablas (migraciones Alembic)

```bash
cd /root/fichajes
source .venv/bin/activate
export FLASK_APP=ejecutar:aplicacion
flask db upgrade
```

Si `flask db upgrade` falla porque nunca hubo migraciones en ese servidor, puede usar **una sola vez** (solo entornos nuevos sin historial):

```bash
python scripts/inicializar_bd.py
```

Lo habitual en un proyecto ya versionado es **`flask db upgrade`**.

**Datos demo** (solo pruebas, no en producción real con datos laborales):

```bash
python scripts/cargar_demo.py
```

---

## 8. Probar Gunicorn a mano (opcional)

```bash
cd /root/fichajes
source .venv/bin/activate
gunicorn --bind 127.0.0.1:8000 wsgi:app
```

En **otra** sesión SSH:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
```

Debería obtener `302` o `200`. Vuelva a la primera sesión y pulse **Ctrl+C** para parar Gunicorn.

---

## 9. Servicio systemd (arranque automático)

Cree el fichero de unidad:

```bash
nano /etc/systemd/system/fichajes.service
```

Pegue **exactamente** (rutas y usuario **root**):

```ini
[Unit]
Description=Control horario (Gunicorn) fichajes.jm2-tech.es
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/fichajes
Environment=PATH=/root/fichajes/.venv/bin
EnvironmentFile=-/root/fichajes/.env
ExecStart=/root/fichajes/.venv/bin/gunicorn \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --bind 127.0.0.1:8000 \
    --access-logfile - \
    --error-logfile - \
    wsgi:app
KillMode=mixed
TimeoutStopSec=30
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Active e inicie el servicio:

```bash
systemctl daemon-reload
systemctl enable fichajes
systemctl start fichajes
systemctl status fichajes
```

Ver logs en vivo:

```bash
journalctl -u fichajes -f
```

Tras cambiar código o `.env`:

```bash
systemctl restart fichajes
```

---

## 10. Nginx — sitio para fichajes.jm2-tech.es

Cree el sitio:

```bash
nano /etc/nginx/sites-available/fichajes.jm2-tech.es
```

Pegue:

```nginx
upstream fichajes_gunicorn {
    server 127.0.0.1:8000 fail_timeout=0;
}

server {
    listen 80;
    listen [::]:80;
    server_name fichajes.jm2-tech.es;

    location / {
        proxy_pass http://fichajes_gunicorn;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_read_timeout 120s;
    }

    client_max_body_size 16M;
}
```

Enlace y prueba de sintaxis:

```bash
ln -sf /etc/nginx/sites-available/fichajes.jm2-tech.es /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

Compruebe por HTTP (desde el VPS):

```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: fichajes.jm2-tech.es" http://127.0.0.1/
```

---

## 11. HTTPS con Let’s Encrypt (Certbot)

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d fichajes.jm2-tech.es
```

Siga el asistente (correo, aceptación de términos, redirección HTTP→HTTPS si se ofrece).

Prueba de renovación:

```bash
certbot renew --dry-run
```

Certbot suele modificar el `server` de Nginx para escuchar en **443** con los certificados. No quite el `proxy_pass` a `127.0.0.1:8000` ni las cabeceras `proxy_set_header`.

---

## 12. Cortafuegos (UFW), si lo usa

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
ufw status
```

---

## 13. Comprobación final

Desde su navegador:

- Abra: **https://fichajes.jm2-tech.es**

Debe cargar la aplicación (login o redirección correcta).

Desde terminal:

```bash
curl -sI https://fichajes.jm2-tech.es | head -n 5
```

---

## 14. PostgreSQL (opcional, en lugar de SQLite)

Si eligió PostgreSQL en el paso 2:

```bash
sudo -u postgres psql -c "CREATE USER fichajes_app WITH PASSWORD 'SU_CLAVE_SEGURA';"
sudo -u postgres psql -c "CREATE DATABASE fichajes OWNER fichajes_app;"
```

En `/root/fichajes/.env`:

```env
DATABASE_URL=postgresql+psycopg2://fichajes_app:SU_CLAVE_SEGURA@127.0.0.1:5432/fichajes
```

Luego:

```bash
cd /root/fichajes
source .venv/bin/activate
export FLASK_APP=ejecutar:aplicacion
flask db upgrade
systemctl restart fichajes
```

---

## 15. Actualizar la aplicación más adelante

```bash
systemctl stop fichajes
cd /root/fichajes
source .venv/bin/activate
git pull
pip install -r requirements.txt -r requirements-prod.txt
export FLASK_APP=ejecutar:aplicacion
flask db upgrade
deactivate
systemctl start fichajes
```

Si no usa Git, sustituya `git pull` por copiar los ficheros nuevos encima y repita `pip` y `flask db upgrade` si hubo cambios.

---

## 16. Copia de seguridad rápida (SQLite)

```bash
cp /root/fichajes/datos/fichajes.db /root/fichajes-backup-$(date +%Y%m%d).db
```

Guarde copias **fuera** del VPS.

---

## 17. Referencia de comandos útiles

| Acción | Comando |
|--------|---------|
| Estado del servicio | `systemctl status fichajes` |
| Reiniciar app | `systemctl restart fichajes` |
| Logs Gunicorn | `journalctl -u fichajes -n 100 --no-pager` |
| Probar Nginx | `nginx -t` |
| Recargar Nginx | `systemctl reload nginx` |

---

## 18. Documentación relacionada

- Variables generales: `.env.example` en el proyecto.
- Notas legales registro horario: `docs/NOTAS_LEGALES.md`.
- Despliegue con usuario dedicado (alternativa a root): `docs/MANUAL_DESPLIEGUE_VPS_UBUNTU_24.md`.

---

*Dominio configurado en este documento: **fichajes.jm2-tech.es** — JM2 Tech.*
