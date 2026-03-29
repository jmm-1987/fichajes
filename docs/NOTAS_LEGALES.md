# Notas legales y decisiones técnicas (España, registro horario)

Este documento resume **decisiones de diseño** alineadas con el registro horario del Real Decreto-ley 8/2019 y buenas prácticas de protección de datos. **No sustituye asesoramiento jurídico.**

## Conservación y disponibilidad

- Los registros de jornada se almacenan en base de datos relacional con **histórico de modificaciones** en tabla de auditoría **append-only** (no se prevé borrado físico de auditoría ni de fichajes).
- La retención mínima de cuatro años es responsabilidad del **responsable del tratamiento** en la instalación del cliente (copias de seguridad, política de archivo y no sobrescritura de backups).
- La aplicación está pensada para que empresa, trabajador e inspección puedan **consultar** registros desde los propios roles (exportación CSV/Excel/PDF).

## Integridad y correcciones

- Una **corrección** de fichaje no borra el registro original: se actualiza el registro conservando trazabilidad mediante **auditoría** (valores anteriores y nuevos en JSON, usuario, rol, motivo, IP, user-agent, origen).
- Las solicitudes de corrección por el empleado generan también evento de auditoría al crearse y al resolverse.

## Geolocalización

- La ubicación se captura **solo en el acto del fichaje** (petición explícita al navegador en el envío del formulario), no hay seguimiento en segundo plano.
- Los datos de ubicación se limitan a coordenadas y precisión (y texto descriptivo opcional); la finalidad es **acreditar el lugar del fichaje**, no el control continuo.

## Protección de datos y privacidad por defecto

- Acceso por **roles**: un empleado solo ve su propio historial y ficha desde el portal asignado; administración y responsables ven según permisos.
- Campos personales y laborales se reducen a lo necesario para la gestión de jornada y vacaciones.

## Multi-tenant

- Instalación **por cliente** (una base de datos por despliegue), no SaaS multi-tenant en este código base.

## Mejoras recomendadas en entorno productivo

- Firma electrónica o registro de integridad (hash encadenado) si el cliente exige mayor prueba técnica frente a manipulación.
- Zona horaria explícita por empresa y calendario laboral completo.
- Política documentada de backups y restauración.
