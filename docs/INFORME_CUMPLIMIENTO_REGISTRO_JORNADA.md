# Informe de cumplimiento — Registro de jornada laboral

**Aplicación:** JM2 Fichajes  
**Normativa de referencia:** Real Decreto-ley 8/2019 y Guía de la Dirección General de Trabajo sobre el registro de jornada (art. 34.9 del Estatuto de los Trabajadores)  
**Fecha del informe:** 19 de mayo de 2026  
**Versión del documento:** 1.0

---

> **Aviso importante**  
> Este documento es una **auditoría técnica** del software frente a criterios orientativos de la guía DGT. **No sustituye asesoramiento jurídico ni laboral.** La interpretación vinculante corresponde a los Juzgados y Tribunales del orden social y a la Inspección de Trabajo y Seguridad Social en cada caso concreto.

---

## 1. Resumen ejecutivo

| Área (según guía DGT) | Valoración global |
|------------------------|-------------------|
| A. Ámbito de aplicación | Cumple en lo esencial |
| B. Contenido y sistema de registro | Cumple parcialmente |
| C. Conservación y acceso | Cumple parcialmente |
| D. Horas extraordinarias (art. 35 ET) | Cumple parcialmente |

**Conclusión:** La aplicación cubre el **núcleo** del deber de registro diario de jornada (marcas de entrada y salida, registro digital, auditoría, informes con referencia al art. 34.9 ET). Existen **brechas** relevantes en el tratamiento de pausas intrajornada, el detalle de jornadas partidas en exportaciones, el acceso del trabajador a su historial completo, el flujo de correcciones aprobadas y la retención documentada de cuatro años (responsabilidad del despliegue).

**Leyenda usada en este informe:**

| Símbolo | Significado |
|---------|-------------|
| ✅ | Cumple |
| ⚠️ | Cumple parcialmente |
| ❌ | No cumple / no implementado |

---

## 2. Marco normativo (síntesis)

Desde el RD-ley 8/2019, las empresas deben llevar un **registro diario de jornada** que incluya el **horario concreto de inicio y finalización** de cada trabajador. La guía DGT aclara, entre otros puntos:

- Aplica a la totalidad de trabajadores en ámbito del ET (con excepciones específicas).
- El sistema puede ser papel o digital, siempre que sea **fiable y trazable**.
- Conviene reflejar **pausas** para no presumir que todo el intervalo entre inicio y fin es tiempo de trabajo efectivo.
- Los registros deben **conservarse cuatro años** y estar **a disposición** del trabajador, sus representantes y la Inspección.
- El registro del art. 34.9 ET es **independiente** del de horas extraordinarias del art. 35 ET, aunque puede usarse el mismo sistema.

---

## 3. Sección A — Ámbito de aplicación

### 3.1 Qué exige la guía

- Registro para trabajadores del ámbito del ET: móviles, comerciales, temporales, teletrabajo, etc.
- Excepciones: personal de alta dirección (art. 2.1.a ET), regímenes especiales, relaciones fuera del ET (autónomos, socios de cooperativas en su régimen societario).
- En ETT: la **empresa usuaria** registra durante la prestación en su ámbito.
- En subcontratación: la **contratista** es responsable; puede acordarse uso del sistema de la principal.

### 3.2 Estado en JM2 Fichajes

| Requisito | Estado | Observaciones |
|-----------|--------|---------------|
| Registro por empleado en ámbito laboral | ✅ | Modelo `Empleado` vinculado a `Empresa` |
| Portal web (móvil / teletrabajo) | ✅ | Ruta `/fichajes/empleado` |
| Terminal público / kiosk sin login | ✅ | Módulo `fichaje_publico` (entrada y salida) |
| Varias empresas en una instalación | ✅ | Multiempresa por `empresa_id` |
| Zona horaria y día laboral local | ✅ | Campo `zona_horaria` en empresa; turnos de noche imputados al día de entrada |
| Gestión de excepciones legales (alta dirección, etc.) | ⚠️ | No hay categoría “exento” en el sistema; depende del alta manual del empleado |
| ETT / empresa usuaria / subcontratación | ❌ | Sin flujos ni campos específicos |
| Cooperativas / autónomos fuera del ET | N/A | No aplicable si no se dan de alta como empleados ET |

---

## 4. Sección B — Contenido y sistema de registro

### 4.1 Inicio, fin y pausas de la jornada

| Requisito | Estado | Observaciones |
|-----------|--------|---------------|
| Registro diario con hora de inicio y fin | ✅ | Tipos `entrada` y `salida` en `RegistroJornada` |
| Registro de pausas intrajornada | ⚠️ | Tipos `pausa_inicio` y `pausa_fin` en portal empleado; **no** en kiosk público |
| Validación de secuencia de marcas | ✅ | `app/fichajes/validadores.py` |
| Pausas entre tramos (jornada partida) | ✅ | Cálculo `horas_pausa_entre_tramos()` (huecos entre salida y nueva entrada) |
| Pausas explícitas descontadas del tiempo trabajado | ❌ | Las marcas PAUSA_* no reducen horas en `construir_segmentos_trabajo()` |
| PDF / informes: todas las marcas del día | ⚠️ | Solo primera entrada y última salida en exportación PDF |
| Incidencias en fichaje | ❌ | Tipo `incidencia` en modelo; sin interfaz de usuario |
| Desplazamientos / tiempo efectivo vs. disponibilidad | ⚠️ | Geolocalización opcional en portal; sin distinción formal “disponibilidad / dieta” |

### 4.2 Medios de registro (digital, trazabilidad, integridad)

| Requisito | Estado | Observaciones |
|-----------|--------|---------------|
| Sistema digital válido | ✅ | Base de datos relacional |
| Fecha/hora de servidor en cada marca | ✅ | Campo `fecha_hora_servidor` |
| Origen, IP, agente de usuario | ✅ | Trazabilidad en alta de fichajes |
| Tabla de auditoría (histórico de cambios) | ✅ | `RegistroAuditoria`, diseño append-only |
| Corrección sin borrado físico | ✅ | `corregir_registro_admin()` con motivo y JSON antes/después |
| Inmutabilidad técnica absoluta (hash, WORM) | ⚠️ | Recomendado en `docs/NOTAS_LEGALES.md`; no implementado en código |
| Consulta previa a representantes (art. 64 ET) | N/A | Proceso organizativo; no modelado en software |

### 4.3 Flexibilidad horaria y teletrabajo

| Requisito | Estado | Observaciones |
|-----------|--------|---------------|
| Registro diario compatible con horario flexible | ✅ | Marcas por día independientes del reparto horario |
| Totalización en periodos superiores (mes) | ⚠️ | Informes por rango de fechas; sin módulo de “bolsa mensual” pactada |
| Teletrabajo con registro telemático | ✅ | Portal empleado + geo opcional en el acto del fichaje |
| Geolocalización respetando intimidad (solo al fichar) | ✅ | `app/fichajes/geolocalizacion.py`; sin seguimiento continuo |

### 4.4 Canales de fichaje

| Canal | Entrada / Salida | Pausas | Geolocalización |
|-------|------------------|--------|-----------------|
| Portal empleado (autenticado) | ✅ | ✅ | ✅ (opcional) |
| Kiosk / fichaje público | ✅ | ❌ | ❌ |
| Corrección por administración | ✅ | — | — |

---

## 5. Sección C — Conservación y acceso

### 5.1 Conservación (4 años)

| Requisito | Estado | Observaciones |
|-----------|--------|---------------|
| Almacenamiento persistente | ✅ | PostgreSQL / SQLite según despliegue |
| Política de retención 4 años en la aplicación | ❌ | Documentado como responsabilidad del cliente (`docs/NOTAS_LEGALES.md`) |
| Purga automática o archivo legal | ❌ | No implementado |

**Recomendación operativa para el responsable del tratamiento:** copias de seguridad diarias, retención de backups ≥ 4 años, política de no sobrescritura y pruebas de restauración documentadas.

### 5.2 Acceso de trabajadores, representantes e inspección

| Requisito | Estado | Observaciones |
|-----------|--------|---------------|
| Empresa: consulta y exportación (CSV, Excel, PDF) | ✅ | Módulo `/informes` (admin, responsable) |
| PDF con pie legal art. 34.9 ET | ✅ | `app/informes/exportadores.py` |
| Trabajador: consulta de su registro | ⚠️ | Historial limitado a 60 marcas |
| Trabajador: exportación PDF/CSV propia | ❌ | Informes restringidos a roles de gestión |
| Representantes legales: acceso | ⚠️ | Vía roles de administración; sin rol “delegado sindical” específico |
| Inspección de Trabajo: acceso | ⚠️ | Sin rol dedicado; la empresa facilita exportación o acceso admin |
| Solicitud de corrección por el empleado | ⚠️ | Ruta existente; sin enlace visible en el portal |
| Aprobación de solicitud aplica el cambio al fichaje | ❌ | `resolver_solicitud_correccion()` no modifica el registro de jornada |

**Nota de la guía DGT:** “A disposición” no exige entregar copia diaria al trabajador, pero sí permitir **consulta** en cualquier momento solicitada.

---

## 6. Sección D — Horas extraordinarias (art. 35 ET)

| Requisito | Estado | Observaciones |
|-----------|--------|---------------|
| Registro diario de jornada (art. 34.9) | ✅ | Obligación cubierta por el sistema de fichajes |
| Cómputo de horas extraordinarias | ⚠️ | `horas_extras = max(0, trabajadas − jornada_teorica)` por día |
| Registro formal de horas extra acordadas / autorizadas | ❌ | No hay módulo específico art. 35 |
| Totalización en periodo de nómina | ⚠️ | Totales en informes; no integración con nómina |
| Entrega de resumen al trabajador en nómina | ❌ | Corresponde al sistema de nómina / RRHH |

---

## 7. Funcionalidades implementadas (fortalezas)

1. **Registro diario multi-canal:** portal empleado y terminal público.
2. **Tipos de marca:** entrada, salida, pausa inicio, pausa fin (portal).
3. **Auditoría** en altas y correcciones administrativas.
4. **Turnos de noche** imputados al día de la entrada.
5. **Configuración laboral** por empresa (jornada teórica, festivos, nocturnas).
6. **Informes y PDF** con datos de empresa (razón social, CIF, centro) y trabajador.
7. **Columna Pausa** en exportaciones (huecos entre tramos del mismo día).
8. **Geolocalización** solo en el acto del fichaje (portal), alineada con protección de datos.
9. **Tests automatizados** de cálculo (segmentos, turno noche, pausa entre tramos).

---

## 8. Brechas y riesgos (priorizados)

| Prioridad | Brecha | Riesgo frente a la guía |
|-----------|--------|-------------------------|
| Alta | Pausas PAUSA_INICIO/FIN no descontan horas trabajadas | Presunción de que todo el intervalo entrada–salida es trabajo efectivo |
| Alta | PDF sin detalle cronológico de marcas | Jornadas partidas poco acreditadas en documento impreso |
| Media | Trabajador sin exportación ni historial completo | Dificultad para ejercer consulta efectiva |
| Media | Aprobar solicitud no corrige el fichaje | Flujo de corrección incompleto |
| Media | Retención 4 años solo documentada | Incumplimiento si el cliente no tiene backups |
| Baja | Kiosk sin pausas | Trabajadores solo en terminal no registran pausas |
| Baja | Sin rol inspección / ETT | Depende de procedimiento manual de la empresa |
| Baja | Sin hash encadenado | Menor prueba técnica ante manipulación |

---

## 9. Plan de mejora recomendado

| # | Acción | Impacto normativo |
|---|--------|-------------------|
| 1 | Descontar tiempo entre PAUSA_INICIO y PAUSA_FIN en cálculos e informes | Alto — alineación con tiempo de trabajo efectivo |
| 2 | Incluir en PDF el listado de marcas del día (hora + tipo) | Alto — prueba de jornadas partidas |
| 3 | Portal empleado: historial por fechas, enlace “Solicitar corrección”, descarga PDF/CSV propia | Medio — acceso del trabajador |
| 4 | Al aprobar solicitud, ejecutar `corregir_registro_admin()` automáticamente | Medio — trazabilidad de correcciones |
| 5 | Checklist de despliegue: backups 4 años, restauración probada | Medio — conservación |
| 6 | Pausas en kiosk (opcional) | Bajo — según uso del terminal |
| 7 | Rol de solo lectura “inspección” o cuenta de auditoría externa (opcional) | Bajo — facilitar ITSS |

---

## 10. Matriz resumen guía DGT → aplicación

| Pregunta / tema (guía) | ¿Cumple? |
|------------------------|----------|
| ¿Registro diario con inicio y fin? | ✅ Sí |
| ¿Pausas reflejadas de forma fiable? | ⚠️ Parcial |
| ¿Sistema digital trazable? | ✅ Sí |
| ¿Inmodificabilidad reforzada (hash)? | ⚠️ Parcial |
| ¿Teletrabajo / fichaje remoto? | ✅ Sí |
| ¿Conservación 4 años garantizada por la app? | ❌ No (cliente) |
| ¿Disposición para trabajador e inspección? | ⚠️ Parcial |
| ¿Horas extraordinarias art. 35 completas? | ⚠️ Parcial |
| ¿ETT / subcontratación? | ❌ No |

---

## 11. Referencias técnicas en el proyecto

| Elemento | Ubicación en el código |
|----------|------------------------|
| Modelo de fichajes | `app/modelos/fichaje.py` |
| Tipos de registro | `app/constantes.py` |
| Cálculos y pausas | `app/fichajes/calculos.py` |
| Servicios y correcciones | `app/fichajes/servicios.py` |
| Exportaciones PDF/CSV/Excel | `app/informes/exportadores.py` |
| Notas legales del producto | `docs/NOTAS_LEGALES.md` |

---

## 12. Firmas y uso del documento

| Campo | Valor |
|-------|-------|
| Elaborado por | _________________________________ |
| Revisado por (RRHH / asesoría) | _________________________________ |
| Fecha de revisión | ____ / ____ / ________ |
| Próxima revisión prevista | ____ / ____ / ________ |

---

*Documento generado para uso interno de la organización. Impresión recomendada: formato A4, márgenes normales, encabezado con nombre de la empresa en la portada si se desea personalizar.*
