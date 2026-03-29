# Módulo de planificación semanal

## Desacoplamiento

- Blueprint `planificacion_bp` registrado solo si `HABILITAR_MODULO_PLANIFICACION=1` en configuración.
- Entidades: `PlanificacionSemanal`, `ItemPlanificacionSemanal`, `PlantillaPlanificacion`, `ItemPlantillaPlanificacion`.

## Funcionalidad

- Creación de semanas por fecha de lunes.
- Tablero por empleado × día (0–6) con hora inicio/fin por celda.
- Duplicar semana a otra fecha.
- Guardar la semana actual como **plantilla** reutilizable.
- Aplicar plantilla a un plan existente.

## Interfaz

- Tabla responsive con formularios por celda (persistencia inmediata).
- Lista de empleados con **arrastrar y soltar** para resaltar celdas (mejora UX; la asignación real sigue siendo explícita al guardar horario).

## Extensión

- Integración futura con turnos rotativos o validación contra fichajes reales.
- Sincronización con calendario corporativo (ICS) como mejora opcional.
