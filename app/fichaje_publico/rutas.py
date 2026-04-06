"""Panel público de fichaje por código (sin sesión de usuario)."""

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.constantes import OrigenRegistroJornada, TipoRegistroJornada
from app.fichaje_publico.servicios import (
    buscar_empleado_por_codigo,
    estado_kiosk_empleado,
    puede_fichar_salida_kiosk,
)
from app.fichajes.servicios import (
    datos_contador_portal_fichaje,
    obtener_registros_dia_ordenados,
    registrar_marca,
)
from app.fichajes.validadores import ahora_servidor

SESSION_KIOSK_EMP = "kiosk_emp_id"

fichaje_publico_bp = Blueprint(
    "fichaje_publico_bp",
    __name__,
    url_prefix="/fichaje-publico",
    template_folder="../plantillas/fichaje_publico",
)


def _kiosk_habilitado() -> bool:
    return bool(current_app.config.get("HABILITAR_FICHAJE_PUBLICO", True))


def _abort_si_deshabilitado():
    if not _kiosk_habilitado():
        abort(404)


@fichaje_publico_bp.route("/", methods=["GET", "POST"])
def inicio():
    """Formulario único: introduce código y fichar entrada o pasar a sesión activa."""
    _abort_si_deshabilitado()
    if request.method == "POST":
        codigo = (request.form.get("codigo") or "").strip()
        emp = buscar_empleado_por_codigo(codigo)
        if not emp:
            flash("Código no reconocido o empleado inactivo.", "peligro")
            return redirect(url_for("fichaje_publico_bp.inicio"))

        est = estado_kiosk_empleado(emp.id)
        if est == "pausa":
            flash(
                "Tiene una pausa abierta. Cierre la pausa desde el móvil o espere a RRHH "
                "antes de fichar salida en este terminal.",
                "aviso",
            )
            return redirect(url_for("fichaje_publico_bp.inicio"))

        if est == "fuera":
            reg, err = registrar_marca(
                empleado_id=emp.id,
                tipo_registro=TipoRegistroJornada.ENTRADA,
                usuario_id=None,
                origen=OrigenRegistroJornada.PANEL_PUBLICO,
                validar_secuencia=True,
            )
            if err or not reg:
                flash(err or "No se pudo registrar la entrada.", "peligro")
                return redirect(url_for("fichaje_publico_bp.inicio"))

            hoy = ahora_servidor().date()
            regs = obtener_registros_dia_ordenados(emp.id, hoy)
            cont = datos_contador_portal_fichaje(regs)
            return render_template(
                "entrada_ok.html",
                empleado=emp,
                contador=cont,
            )

        # dentro: guardar sesión y mostrar pantalla con tiempo + detener
        session[SESSION_KIOSK_EMP] = emp.id
        session.permanent = False
        return redirect(url_for("fichaje_publico_bp.sesion_activa"))

    session.pop(SESSION_KIOSK_EMP, None)
    return render_template("inicio.html")


@fichaje_publico_bp.route("/sesion", methods=["GET"])
def sesion_activa():
    """Muestra tiempo trabajado y botón para fichar salida (tras validar código)."""
    _abort_si_deshabilitado()
    eid = session.get(SESSION_KIOSK_EMP)
    if not eid:
        flash("Introduzca su código en la pantalla inicial.", "aviso")
        return redirect(url_for("fichaje_publico_bp.inicio"))

    from app.modelos import Empleado

    emp = Empleado.query.get(eid)
    if not emp or not emp.activo:
        session.pop(SESSION_KIOSK_EMP, None)
        flash("Sesión no válida.", "peligro")
        return redirect(url_for("fichaje_publico_bp.inicio"))

    est = estado_kiosk_empleado(emp.id)
    if est != "dentro" or not puede_fichar_salida_kiosk(emp.id):
        session.pop(SESSION_KIOSK_EMP, None)
        if est == "pausa":
            flash(
                "Pausa abierta: use el móvil para fin de pausa o salga desde allí.",
                "aviso",
            )
        else:
            flash("La jornada ya está cerrada. Introduzca el código de nuevo.", "aviso")
        return redirect(url_for("fichaje_publico_bp.inicio"))

    hoy = ahora_servidor().date()
    regs = obtener_registros_dia_ordenados(emp.id, hoy)
    cont = datos_contador_portal_fichaje(regs)

    return render_template(
        "sesion_activa.html",
        empleado=emp,
        contador=cont,
    )


@fichaje_publico_bp.route("/salida", methods=["POST"])
def fichar_salida():
    _abort_si_deshabilitado()
    eid = session.get(SESSION_KIOSK_EMP)
    if not eid:
        flash("Sesión caducada. Introduzca el código otra vez.", "peligro")
        return redirect(url_for("fichaje_publico_bp.inicio"))

    from app.modelos import Empleado

    emp = Empleado.query.get(eid)
    if not emp or not emp.activo:
        session.pop(SESSION_KIOSK_EMP, None)
        flash("Sesión no válida.", "peligro")
        return redirect(url_for("fichaje_publico_bp.inicio"))

    if not puede_fichar_salida_kiosk(emp.id):
        session.pop(SESSION_KIOSK_EMP, None)
        flash("No se puede fichar salida en este momento.", "peligro")
        return redirect(url_for("fichaje_publico_bp.inicio"))

    reg, err = registrar_marca(
        empleado_id=emp.id,
        tipo_registro=TipoRegistroJornada.SALIDA,
        usuario_id=None,
        origen=OrigenRegistroJornada.PANEL_PUBLICO,
        validar_secuencia=True,
    )
    session.pop(SESSION_KIOSK_EMP, None)

    if err or not reg:
        flash(err or "No se pudo registrar la salida.", "peligro")
        return redirect(url_for("fichaje_publico_bp.inicio"))

    return render_template("salida_ok.html", empleado=emp)
