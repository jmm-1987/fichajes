"""Constantes de dominio (roles, estados, tipos)."""


class RolUsuario:
    """Roles reconocidos por la aplicación."""

    SUPERADMINISTRADOR = "superadministrador"
    ADMINISTRADOR_EMPRESA = "administrador_empresa"
    RESPONSABLE = "responsable"
    EMPLEADO = "empleado"


class TipoRegistroJornada:
    """Tipos de marca de fichaje."""

    ENTRADA = "entrada"
    SALIDA = "salida"
    PAUSA_INICIO = "pausa_inicio"
    PAUSA_FIN = "pausa_fin"
    INCIDENCIA = "incidencia"
    CORRECCION = "correccion"


class EstadoRegistroJornada:
    """Estado del registro de jornada."""

    VALIDO = "valido"
    PENDIENTE_REVISION = "pendiente_revision"
    CORREGIDO = "corregido"
    ANULADO = "anulado"


class OrigenRegistroJornada:
    """Origen del fichaje."""

    WEB_EMPLEADO = "web_empleado"
    ADMIN = "admin"
    IMPORTACION = "importacion"
    AJUSTE = "ajuste"


class EstadoSolicitudCorreccion:
    """Estado de una solicitud de corrección."""

    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"


class EstadoSolicitudVacaciones:
    """Estado de solicitud de vacaciones."""

    PENDIENTE = "pendiente"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    DISFRUTADO = "disfrutado"


class AmbitoFestivo:
    """Ámbito del festivo."""

    NACIONAL = "nacional"
    AUTONOMICO = "autonomico"
    LOCAL = "local"


class TipoAccionAuditoria:
    """Acciones registradas en auditoría."""

    CREAR = "crear"
    ACTUALIZAR = "actualizar"
    ANULAR = "anular"
    APROBAR = "aprobar"
    RECHAZAR = "rechazar"
