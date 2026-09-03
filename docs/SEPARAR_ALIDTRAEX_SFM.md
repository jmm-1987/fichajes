# Separar Alditraex y SFM en el mismo VPS

**Qué se comparte:** solo la máquina (el VPS).

**Qué se separa:** carpeta, entorno Python, `.env`, `SECRET_KEY`, base de datos, unidad systemd, Nginx, certificado TLS y URL.

La instalación actual **sigue funcionando** en `https://fichajes.jm2-tech.es` hasta que las dos copias estén probadas. No se para, no se renombra, no se desactiva `fichajes.service` hasta el corte final.

Dos copias en paralelo, cada una con su subdominio:

- `https://fichajes-alditraex.jm2-tech.es`
- `https://fichajes-sfm.jm2-tech.es`

---

## Cómo está ahora

Una sola app, una sola URL, una sola BD `fichajes`:

- App: `https://fichajes.jm2-tech.es` → Gunicorn `127.0.0.1:8000` → `/srv/fichajes`
- Kiosco Alditraex: `https://fichajes.jm2-tech.es/fichaje-publico`
- Kiosco SFM: `https://fichajes.jm2-tech.es/fichaje_publico_sfm234r`

## Cómo queda durante las pruebas (las tres vivas)

| | Actual (no tocar) | Copia Alditraex | Copia SFM |
|---|---|---|---|
| Carpeta | `/srv/fichajes` | `/srv/fichajes-alditraex` | `/srv/fichajes-sfm` |
| systemd | `fichajes` | `fichajes-alditraex` | `fichajes-sfm` |
| Puerto | `127.0.0.1:8000` | `127.0.0.1:8001` | `127.0.0.1:8002` |
| BD | `fichajes` | `fichajes_alditraex` | `fichajes_sfm` |
| URL | `https://fichajes.jm2-tech.es` | `https://fichajes-alditraex.jm2-tech.es` | `https://fichajes-sfm.jm2-tech.es` |

Usuario systemd en las tres: `fichajes` / grupo `www-data`.

Los puertos 8001 y 8002 son para no chocar con la app que ya está en 8000.

## Cómo queda después del corte

La URL vieja redirige a Alditraex. La unidad `fichajes` se apaga. Quedan solo las dos copias.

---

## 0. Antes de tocar nada

```bash
ls /etc/nginx/sites-enabled/
```

El `ExecStart` de `fichajes.service` está cortado en pantalla. En las unidades nuevas copie **la línea entera** de gunicorn y cambie solo ruta y puerto.

### DNS

Dos registros **A** a la **misma IP** que `fichajes.jm2-tech.es`. Dejar `fichajes` como está.

| Nombre | Tipo | Valor |
|--------|------|--------|
| `fichajes-alditraex` | A | IP pública del VPS |
| `fichajes-sfm` | A | la misma IP |

```bash
ping -c 2 fichajes-alditraex.jm2-tech.es
ping -c 2 fichajes-sfm.jm2-tech.es
```

Hasta que resuelvan, no se pueden pedir los certificados.

---

## 1. Inventario (qué id es cada empresa)

En la BD **actual** (sigue en uso):

```bash
sudo -u postgres psql fichajes -c "SELECT id, nombre, cif, activa FROM empresas ORDER BY id;"
```

Anotar (producción):

| id | Nombre | Usuarios con `empresa_id` | Empleados | Fichajes |
|----|--------|---------------------------|-----------|----------|
| **12** | Alditraex Merida | 1 (manager) | **28** | **4592** |
| **13** | SFM | 1 (manager) | **7** | **347** |
| **1** | Empresa por defecto | 0 | **0** | **0** |
| *(NULL)* | — | **36** (los 35 empleados + superadmin; no tienen `empresa_id` en `usuarios`) | — | — |

La empresa `1` está vacía: en las dos copias se borra.  
Los 36 usuarios sin empresa no se pueden borrar con `WHERE empresa_id = 13`: hay que borrar los `usuario_id` de los empleados que se quitan. El recorte del paso 8 ya lo contempla. El superadmin no tiene ficha de empleado y se queda en las dos copias.

Conteos (una línea cada uno, comillas cerradas):

```bash
sudo -u postgres psql fichajes -c "SELECT empresa_id, COUNT(*) FROM usuarios GROUP BY empresa_id;"
sudo -u postgres psql fichajes -c "SELECT empresa_id, COUNT(*) FROM empleados GROUP BY empresa_id;"
sudo -u postgres psql fichajes -c "SELECT e.empresa_id, COUNT(*) FROM registros_jornada r JOIN empleados e ON e.id = r.empleado_id GROUP BY e.empresa_id;"
```

Guardar esos números.

---

## 2. Backup (sin parar nada)

```bash
cp -a /srv/fichajes /srv/fichajes.bak-$(date +%Y%m%d)
sudo -u postgres pg_dump -Fc fichajes > /root/fichajes-antes-separar-$(date +%Y%m%d).dump
```

La app actual sigue en marcha.

---

## 3. Dos copias de la carpeta (sin `mv`)

**No parar** `fichajes`. **No** mover `/srv/fichajes`.

```bash
cp -a /srv/fichajes /srv/fichajes-alditraex
cp -a /srv/fichajes /srv/fichajes-sfm
chown -R fichajes:www-data /srv/fichajes-alditraex /srv/fichajes-sfm
```

Quedan **tres** carpetas:

- `/srv/fichajes` ← producción, no se toca
- `/srv/fichajes-alditraex`
- `/srv/fichajes-sfm`

---

## 4. Dos bases PostgreSQL (la original no se toca)

Clonar `fichajes` **dos veces**. La original sigue sirviendo la app actual.

```bash
sudo -u postgres psql -c "CREATE DATABASE fichajes_alditraex OWNER fichajes_app;"
sudo -u postgres psql -c "CREATE DATABASE fichajes_sfm OWNER fichajes_app;"
sudo -u postgres pg_dump fichajes | sudo -u postgres psql fichajes_alditraex
sudo -u postgres pg_dump fichajes | sudo -u postgres psql fichajes_sfm
```

```bash
sudo -u postgres psql -c "\l" | grep fichajes
```

Deben existir las tres: `fichajes`, `fichajes_alditraex`, `fichajes_sfm`.

---

## 5. `.env` solo en las copias

No editar `/srv/fichajes/.env`.

En `/srv/fichajes-alditraex/.env` y `/srv/fichajes-sfm/.env`:

1. `SECRET_KEY` **distinta** en cada copia. En el VPS:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Ejecutar **dos veces**. Pegar una clave en `/srv/fichajes-alditraex/.env` y la otra en `/srv/fichajes-sfm/.env`. No reutilizar la de producción.
2. `DATABASE_URL` a **su** BD (mismo usuario y clave; cambia el nombre final):

```env
# /srv/fichajes-alditraex/.env
DATABASE_URL=postgresql+psycopg2://fichajes_app:LA_MISMA_CLAVE@127.0.0.1:5432/fichajes_alditraex

# /srv/fichajes-sfm/.env
DATABASE_URL=postgresql+psycopg2://fichajes_app:LA_MISMA_CLAVE@127.0.0.1:5432/fichajes_sfm
```

Si una copia apunta a `/fichajes`, escribiría en producción. Comprobarlo.

3. `DETRAS_DE_PROXY=1`

---

## 6. systemd: dos unidades **nuevas** (la actual se queda)

**No** hacer `systemctl disable fichajes`.

Puertos: original **8000**, Alditraex **8001**, SFM **8002**.

Si gunicorn no usa `ejecutar:aplicacion`, copie el final de la línea original.

`/etc/systemd/system/fichajes-alditraex.service`:

```ini
[Unit]
Description=Fichajes Alditraex Gunicorn
After=network.target

[Service]
User=fichajes
Group=www-data
WorkingDirectory=/srv/fichajes-alditraex
EnvironmentFile=/srv/fichajes-alditraex/.env
ExecStart=/srv/fichajes-alditraex/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8001 ejecutar:aplicacion
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/fichajes-sfm.service`:

```ini
[Unit]
Description=Fichajes SFM Gunicorn
After=network.target

[Service]
User=fichajes
Group=www-data
WorkingDirectory=/srv/fichajes-sfm
EnvironmentFile=/srv/fichajes-sfm/.env
ExecStart=/srv/fichajes-sfm/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8002 ejecutar:aplicacion
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now fichajes-alditraex fichajes-sfm
systemctl status fichajes fichajes-alditraex fichajes-sfm
```

Las tres deben estar `active`. `https://fichajes.jm2-tech.es` sigue igual.

---

## 7. Nginx + HTTPS de las copias (sin tocar el sitio actual)

Dos sitios nuevos. El de `fichajes.jm2-tech.es` **no se modifica** todavía.

### Alditraex → puerto 8001

```bash
nano /etc/nginx/sites-available/fichajes-alditraex.jm2-tech.es
```

```nginx
upstream fichajes_alditraex_gunicorn {
    server 127.0.0.1:8001 fail_timeout=0;
}

server {
    listen 80;
    listen [::]:80;
    server_name fichajes-alditraex.jm2-tech.es;

    location / {
        proxy_pass http://fichajes_alditraex_gunicorn;
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

### SFM → puerto 8002

El `upstream` **no** puede llamarse igual que el de Alditraex.

```bash
nano /etc/nginx/sites-available/fichajes-sfm.jm2-tech.es
```

Borra el contenido (si copiaste el de Alditraex) y deja **esto**:

```nginx
upstream fichajes_sfm_gunicorn {
    server 127.0.0.1:8002 fail_timeout=0;
}

server {
    listen 80;
    listen [::]:80;
    server_name fichajes-sfm.jm2-tech.es;

    location / {
        proxy_pass http://fichajes_sfm_gunicorn;
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

```bash
ln -sf /etc/nginx/sites-available/fichajes-alditraex.jm2-tech.es /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/fichajes-sfm.jm2-tech.es /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

certbot --nginx -d fichajes-alditraex.jm2-tech.es
certbot --nginx -d fichajes-sfm.jm2-tech.es
```

En este punto se puede entrar a las tres URLs. Las copias aún verán las **dos** empresas (el recorte es el paso 8). La producción no se ha enterado.

---

## 8. Recortar datos **solo en las copias**

**Prohibido** ejecutar estos `DELETE` en la BD `fichajes`. Solo en `fichajes_alditraex` y `fichajes_sfm`.

| BD | Dejar | Quitar |
|----|--------|--------|
| `fichajes_alditraex` | `12` Alditraex Merida | `13` SFM y `1` Empresa por defecto |
| `fichajes_sfm` | `13` SFM | `12` Alditraex y `1` Empresa por defecto |

Casi todos los empleados tienen `usuarios.empresa_id` a NULL. Hay que guardar sus `usuario_id` **antes** de borrar empleados. No cambiar IDs. Si algo falla: `ROLLBACK`.

```bash
sudo -u postgres psql fichajes_alditraex
```

```sql
BEGIN;

CREATE TEMP TABLE _uids AS
SELECT usuario_id AS id FROM empleados WHERE empresa_id IN (13, 1)
UNION
SELECT id FROM usuarios WHERE empresa_id IN (13, 1);

DELETE FROM solicitudes_correccion
 WHERE empleado_id IN (SELECT id FROM empleados WHERE empresa_id IN (13, 1));
DELETE FROM registros_jornada
 WHERE empleado_id IN (SELECT id FROM empleados WHERE empresa_id IN (13, 1));
DELETE FROM solicitudes_vacaciones
 WHERE empleado_id IN (SELECT id FROM empleados WHERE empresa_id IN (13, 1));
DELETE FROM clasificaciones_dia_laboral
 WHERE empleado_id IN (SELECT id FROM empleados WHERE empresa_id IN (13, 1));
DELETE FROM items_planificacion_semanal
 WHERE empleado_id IN (SELECT id FROM empleados WHERE empresa_id IN (13, 1));
DELETE FROM items_plantilla_planificacion
 WHERE empleado_id IN (SELECT id FROM empleados WHERE empresa_id IN (13, 1));

DELETE FROM planificaciones_semanales
 WHERE id NOT IN (
     SELECT DISTINCT planificacion_semanal_id FROM items_planificacion_semanal
 );

DELETE FROM empleados WHERE empresa_id IN (13, 1);
DELETE FROM usuarios WHERE id IN (SELECT id FROM _uids);

DELETE FROM festivos WHERE empresa_id IN (13, 1);
DELETE FROM configuracion_horas_nocturnas WHERE empresa_id IN (13, 1);
DELETE FROM configuracion_aplicacion
 WHERE clave LIKE 'empresa:13:%' OR clave LIKE 'empresa:1:%';
DELETE FROM empresas WHERE id IN (13, 1);

COMMIT;
```

En `fichajes_sfm` el mismo script cambiando **13** por **12** (quitar Alditraex; el `1` se quita igual).

```bash
sudo -u postgres psql fichajes_sfm
```

Sustituir `IN (13, 1)` por `IN (12, 1)` y `'empresa:13:%'` por `'empresa:12:%'`.

La tabla `registros_auditoria` no se borra.

---

## 9. Probar las copias (producción sigue)

En cada BD clonada:

```sql
SELECT id, nombre FROM empresas;
SELECT empresa_id, COUNT(*) FROM empleados GROUP BY empresa_id;
SELECT e.empresa_id, COUNT(*)
FROM registros_jornada r
JOIN empleados e ON e.id = r.empleado_id
GROUP BY e.empresa_id;
```

- Cada copia: una sola empresa; conteos ≈ inventario del paso 1 (puede faltar lo fichado **después** del `pg_dump`).
- `https://fichajes.jm2-tech.es` sigue con las dos empresas, como siempre.

Pruebas en las URLs **nuevas**:

1. Login Alditraex en `https://fichajes-alditraex.jm2-tech.es` (sin gente de SFM).
2. Login SFM en `https://fichajes-sfm.jm2-tech.es` (sin gente de Alditraex).
3. Un fichaje de prueba en cada copia (queda en su BD, no en producción).
4. Kiosco Alditraex: `https://fichajes-alditraex.jm2-tech.es/fichaje-publico`
5. Kiosco SFM: `https://fichajes-sfm.jm2-tech.es/fichaje_publico_sfm234r`

Mientras se prueba, la gente puede seguir fichando en la URL vieja. Esos registros **no** entran solos en las copias.

---

## 10. Corte (solo cuando las copias estén bien)

Antes del corte, las copias están desfasadas respecto a producción. Hay que refrescar datos:

1. Avisar: unos minutos sin fichar, o parar `fichajes` un momento.
2. Volver a volcar y recortar **las copias** (no la original):

```bash
systemctl stop fichajes

sudo -u postgres dropdb fichajes_alditraex
sudo -u postgres dropdb fichajes_sfm
sudo -u postgres psql -c "CREATE DATABASE fichajes_alditraex OWNER fichajes_app;"
sudo -u postgres psql -c "CREATE DATABASE fichajes_sfm OWNER fichajes_app;"
sudo -u postgres pg_dump fichajes | sudo -u postgres psql fichajes_alditraex
sudo -u postgres pg_dump fichajes | sudo -u postgres psql fichajes_sfm
```

3. Repetir el recorte SQL del paso 8 en las dos BD nuevas.
4. `systemctl restart fichajes-alditraex fichajes-sfm`
5. Comprobar login y un fichaje en cada URL nueva.
6. Redirigir la URL vieja a Alditraex (editar el sitio de `fichajes.jm2-tech.es`):

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name fichajes.jm2-tech.es;
    return 301 https://fichajes-alditraex.jm2-tech.es$request_uri;
}

# En el bloque 443 del mismo nombre, lo mismo:
# return 301 https://fichajes-alditraex.jm2-tech.es$request_uri;
```

El kiosco de SFM no se redirige bien (iría a Alditraex): hay que apuntar la tablet a `https://fichajes-sfm.jm2-tech.es/fichaje_publico_sfm234r`.

7. Dejar `fichajes` parado (`systemctl disable fichajes`). No borrar `/srv/fichajes` ni la BD `fichajes` hasta unos días después.

Si algo sale mal: quitar la redirección, `systemctl start fichajes`, producción vuelve.

---

## 11. Después de unos días (opcional)

- Borrar backup, carpeta `/srv/fichajes` y BD `fichajes` cuando ya no hagan falta.
- Quitar `fichajes.service`.

---

## Orden resumido

1. DNS de los dos subdominios.
2. Inventario en la BD `fichajes`.
3. Backup (app actual encendida).
4. `cp -a` a `/srv/fichajes-alditraex` y `/srv/fichajes-sfm` (**sin** `mv`).
5. Clonar BD a `fichajes_alditraex` y `fichajes_sfm`.
6. `.env` de las copias (nunca el de producción).
7. systemd nuevos en 8001 y 8002; `fichajes` sigue en 8000.
8. Nginx + Certbot de los subdominios.
9. Recorte **solo** en las BD copias.
10. Probar las URLs nuevas. Producción intacta.
11. Corte: volcado fresco + recorte + redirección + apagar `fichajes`.

Logs:

```bash
journalctl -u fichajes -e
journalctl -u fichajes-alditraex -e
journalctl -u fichajes-sfm -e
```
