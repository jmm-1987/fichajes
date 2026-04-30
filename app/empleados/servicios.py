"""Lógica de negocio de empleados."""

from calendar import monthrange
from datetime import date
from decimal import Decimal
import secrets
import string

from app.administracion.servicios import obtener_config_empresa
from app.auditoria.servicios import registrar_auditoria
from app.constantes import TipoAccionAuditoria
from app.extensiones import db
from app.fichajes.calculos import calcular_resumen_periodo
from app.modelos import Empleado, Usuario


def generar_codigo_fichaje_unico(longitud: int = 4) -> str:
    """Genera un código alfanumérico único global para fichaje."""
    alfabeto = string.ascii_uppercase + string.digits
    for _ in range(200):
        codigo = "".join(secrets.choice(alfabeto) for _ in range(longitud))
        existe = Empleado.query.filter_by(codigo_empleado=codigo).first()
        if not existe:
            return codigo
    raise ValueError(
        "No se pudo generar un código de fichaje único. Intente de nuevo."
    )


def tipos_empleado_configurados(empresa_id: int) -> list[str]:
    """Etiquetas de tipo definidas en parámetros de la empresa (una por línea)."""
    cfg = obtener_config_empresa(empresa_id, "tipos_empleado", "")
    raw = (cfg.valor or "").strip()
    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def opciones_select_tipo_empleado(
    empresa_id: int | None, valor_actual: str | None
) -> list[tuple[str, str]]:
    """Opciones para el desplegable: sin asignar, tipos de empresa y valor huérfano."""
    opts: list[tuple[str, str]] = [("", "— Sin asignar —")]
    vac = (valor_actual or "").strip() or None
    if not empresa_id:
        if vac:
            opts.append((vac, vac))
        return opts
    tipos = tipos_empleado_configurados(empresa_id)
    if vac and vac not in tipos:
        opts.append((vac, f"{vac} (ya no en lista)"))
    for t in tipos:
        opts.append((t, t))
    return opts


def validar_tipo_empleado_para_guardar(
    empresa_id: int | None,
    valor_formulario: str | None,
    valor_previo: str | None = None,
) -> str | None:
    """Normaliza tipo; comprueba que exista en la lista salvo valor previo igual."""
    s = (valor_formulario or "").strip()
    if not s:
        return None
    if not empresa_id:
        raise ValueError(
            "No hay empresa asociada; no se puede asignar tipo de empleado."
        )
    tipos = tipos_empleado_configurados(empresa_id)
    if s in tipos:
        return s
    prev = (valor_previo or "").strip() or None
    if prev and s == prev:
        return s
    raise ValueError(
        "El tipo de empleado debe figurar en la configuración laboral de la empresa "
        "(tipos de empleado)."
    )


def crear_empleado_con_usuario(
    datos: dict,
    contrasena: str | None,
    rol: str,
) -> Empleado:
    """Crea usuario y ficha de empleado."""
    usuario = Usuario(
        correo_electronico=(datos["correo_electronico"] or "").strip().lower(),
        rol=rol,
        activo=True,
    )
    if not contrasena:
        raise ValueError("La contraseña es obligatoria en el alta.")
    usuario.establecer_contrasena(contrasena)
    db.session.add(usuario)
    db.session.flush()

    saldo = datos.get("saldo_vacaciones")
    if saldo is None:
        saldo = datos.get("vacaciones_anuales", 22)

    codigo_fichaje = generar_codigo_fichaje_unico()

    emp_kwargs = dict(
        usuario_id=usuario.id,
        codigo_empleado=codigo_fichaje,
        nombre=datos["nombre"].strip(),
        apellidos=datos["apellidos"].strip(),
        telefono=(datos.get("telefono") or "").strip() or None,
        documento_identidad=(datos.get("documento_identidad") or "").strip()
        or None,
        fecha_alta=datos["fecha_alta"],
        horas_semanales=Decimal(str(datos["horas_semanales"])),
        vacaciones_anuales=int(Decimal(str(datos["vacaciones_anuales"]))),
        saldo_vacaciones=Decimal(str(saldo)),
        tipo_contrato=(datos.get("tipo_contrato") or "").strip() or None,
        activo=bool(datos.get("activo", True)),
        centro_trabajo=(datos.get("centro_trabajo") or "").strip() or None,
        responsable_id=None,
        responsable_usuario_id=datos.get("responsable_usuario_id") or None,
        observaciones=(datos.get("observaciones") or "").strip() or None,
    )
    # Empresa: si viene en datos la usamos; si no, heredamos empresa del usuario actual
    # (primero desde su ficha de empleado, y si no, desde usuario.empresa_id).
    from flask_login import current_user

    empresa_id = datos.get("empresa_id")
    if empresa_id is None:
        emp_actual = getattr(current_user, "empleado", None)
        if emp_actual is not None:
            empresa_id = emp_actual.empresa_id
        else:
            empresa_id = getattr(current_user, "empresa_id", None)
    if empresa_id is not None:
        emp_kwargs["empresa_id"] = empresa_id

    te = validar_tipo_empleado_para_guardar(
        empresa_id,
        datos.get("tipo_empleado"),
        None,
    )
    emp_kwargs["tipo_empleado"] = te

    emp = Empleado(**emp_kwargs)
    db.session.add(emp)
    db.session.flush()
    registrar_auditoria(
        tipo_entidad="empleado",
        id_entidad=emp.id,
        accion=TipoAccionAuditoria.CREAR,
        estado_nuevo={"codigo": emp.codigo_empleado, "nombre": emp.nombre_completo},
        motivo="Alta de empleado",
        usuario_actor_id=None,
    )
    db.session.commit()
    return emp


def actualizar_empleado(empleado: Empleado, datos: dict, nueva_contrasena: str | None):
    """Actualiza ficha; opcionalmente cambia contraseña del usuario."""
    antes = {
        "nombre": empleado.nombre,
        "apellidos": empleado.apellidos,
        "activo": empleado.activo,
    }
    empleado.nombre = datos["nombre"].strip()
    empleado.apellidos = datos["apellidos"].strip()
    empleado.telefono = (datos.get("telefono") or "").strip() or None
    empleado.documento_identidad = (
        (datos.get("documento_identidad") or "").strip() or None
    )
    empleado.fecha_alta = datos["fecha_alta"]
    empleado.horas_semanales = Decimal(str(datos["horas_semanales"]))
    empleado.vacaciones_anuales = int(Decimal(str(datos["vacaciones_anuales"])))
    if datos.get("saldo_vacaciones") is not None:
        empleado.saldo_vacaciones = Decimal(str(datos["saldo_vacaciones"]))
    empleado.tipo_contrato = (datos.get("tipo_contrato") or "").strip() or None
    empleado.activo = bool(datos.get("activo", True))
    empleado.centro_trabajo = (datos.get("centro_trabajo") or "").strip() or None
    empleado.responsable_id = datos.get("responsable_id") or None
    if "responsable_usuario_id" in datos:
        empleado.responsable_usuario_id = datos.get("responsable_usuario_id") or None
    empleado.observaciones = (datos.get("observaciones") or "").strip() or None
    empleado.tipo_empleado = validar_tipo_empleado_para_guardar(
        empleado.empresa_id,
        datos.get("tipo_empleado"),
        empleado.tipo_empleado,
    )

    usuario = empleado.usuario
    usuario.correo_electronico = (datos["correo_electronico"] or "").strip().lower()
    usuario.rol = datos["rol"]
    if nueva_contrasena:
        usuario.establecer_contrasena(nueva_contrasena)

    despues = {
        "nombre": empleado.nombre,
        "apellidos": empleado.apellidos,
        "activo": empleado.activo,
    }
    registrar_auditoria(
        tipo_entidad="empleado",
        id_entidad=empleado.id,
        accion=TipoAccionAuditoria.ACTUALIZAR,
        estado_anterior=antes,
        estado_nuevo=despues,
        motivo="Actualización de ficha",
    )
    db.session.commit()


def resumen_mes_actual(empleado_id: int) -> dict:
    """Horas agregadas del mes en curso."""
    hoy = date.today()
    inicio = date(hoy.year, hoy.month, 1)
    ultimo = monthrange(hoy.year, hoy.month)[1]
    fin_mes = date(hoy.year, hoy.month, ultimo)
    fin = min(hoy, fin_mes)
    return calcular_resumen_periodo(empleado_id, inicio, fin)


def vacaciones_resumen(empleado: Empleado) -> dict:
    """Días disfrutados y pendientes aproximados desde solicitudes."""
    from app.constantes import EstadoSolicitudVacaciones
    from app.modelos import SolicitudVacaciones

    aprob_disfrutadas = (
        SolicitudVacaciones.query.filter_by(
            empleado_id=empleado.id,
            estado=EstadoSolicitudVacaciones.DISFRUTADO,
        ).all()
    )
    dias_disfrutados = sum(float(s.numero_dias) for s in aprob_disfrutadas)
    pendientes_aprob = (
        SolicitudVacaciones.query.filter_by(
            empleado_id=empleado.id,
            estado=EstadoSolicitudVacaciones.PENDIENTE,
        ).count()
    )
    return {
        "saldo": float(empleado.saldo_vacaciones),
        "anuales": empleado.vacaciones_anuales,
        "disfrutados_registrados": dias_disfrutados,
        "solicitudes_pendientes": pendientes_aprob,
    }
