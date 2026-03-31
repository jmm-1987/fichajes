"""Vistas de informes y exportaciones."""

from datetime import date

from flask import Blueprint, make_response, render_template, request
from flask_login import login_required

from app.constantes import RolUsuario
from app.extensiones import db
from app.informes.exportadores import exportar_csv, exportar_excel, exportar_pdf
from app.informes.servicios import FiltrosInforme, centros_distintos, construir_informe_empleado
from app.modelos import Empleado
from app.utilidades.fechas import parsear_fecha_es, periodo_texto
from app.utilidades.predicados import roles_permitidos

informes_bp = Blueprint(
    "informes_bp",
    __name__,
    url_prefix="/informes",
    template_folder="../plantillas/informes",
)


def _parse_fecha(nombre: str, defecto: date) -> date:
    raw = request.args.get(nombre)
    if not raw:
        return defecto
    p = parsear_fecha_es(raw)
    return p if p is not None else defecto


@informes_bp.route("/")
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def indice():
    hoy = date.today()
    ini = date(hoy.year, hoy.month, 1)
    f = FiltrosInforme(
        fecha_inicio=_parse_fecha("desde", ini),
        fecha_fin=_parse_fecha("hasta", hoy),
        empleado_id=request.args.get("empleado_id", type=int),
        centro_trabajo=request.args.get("centro") or None,
        equipo_responsable_id=request.args.get("responsable_id", type=int),
        incluir_extras=request.args.get("extras", "1") == "1",
        incluir_nocturnas=request.args.get("nocturnas", "1") == "1",
        incluir_festivas=request.args.get("festivas", "1") == "1",
        solo_incidencias=request.args.get("solo_incidencias", "0") == "1",
        solo_incompletos=request.args.get("solo_incompletos", "0") == "1",
    )
    filas = construir_informe_empleado(f)

    emp_q = Empleado.query.filter_by(activo=True)
    # Filtrar por empresa del usuario actual (salvo superadmin)
    from flask_login import current_user
    from app.constantes import RolUsuario

    if current_user.rol != RolUsuario.SUPERADMINISTRADOR:
        emp_actual = getattr(current_user, "empleado", None)
        if emp_actual:
            emp_q = emp_q.filter(Empleado.empresa_id == emp_actual.empresa_id)

    empleados = emp_q.order_by(Empleado.apellidos).all()

    ids_resp = [
        r[0]
        for r in db.session.query(Empleado.responsable_id)
        .filter(Empleado.responsable_id.isnot(None))
        .distinct()
    ]
    if ids_resp:
        responsables_objs = Empleado.query.filter(Empleado.id.in_(ids_resp)).all()
    else:
        responsables_objs = []

    # Ruta explícita: evita colisión con planificacion/indice.html (mismo nombre de fichero).
    return render_template(
        "informes/indice.html",
        filas=filas,
        filtros=f,
        empleados=empleados,
        centros=centros_distintos(),
        responsables=responsables_objs,
    )


@informes_bp.route("/exportar/csv")
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def exportar_csv_vista():
    hoy = date.today()
    ini = date(hoy.year, hoy.month, 1)
    f = FiltrosInforme(
        fecha_inicio=_parse_fecha("desde", ini),
        fecha_fin=_parse_fecha("hasta", hoy),
        empleado_id=request.args.get("empleado_id", type=int),
        centro_trabajo=request.args.get("centro") or None,
        equipo_responsable_id=request.args.get("responsable_id", type=int),
    )
    filas = construir_informe_empleado(f)
    data = exportar_csv(filas)
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=informe_fichajes.csv"
    return resp


@informes_bp.route("/exportar/excel")
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def exportar_excel_vista():
    hoy = date.today()
    ini = date(hoy.year, hoy.month, 1)
    f = FiltrosInforme(
        fecha_inicio=_parse_fecha("desde", ini),
        fecha_fin=_parse_fecha("hasta", hoy),
        empleado_id=request.args.get("empleado_id", type=int),
        centro_trabajo=request.args.get("centro") or None,
        equipo_responsable_id=request.args.get("responsable_id", type=int),
    )
    filas = construir_informe_empleado(f)
    data = exportar_excel(filas)
    resp = make_response(data)
    resp.headers["Content-Type"] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp.headers["Content-Disposition"] = "attachment; filename=informe_fichajes.xlsx"
    return resp


@informes_bp.route("/exportar/pdf")
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def exportar_pdf_vista():
    hoy = date.today()
    ini = date(hoy.year, hoy.month, 1)
    f = FiltrosInforme(
        fecha_inicio=_parse_fecha("desde", ini),
        fecha_fin=_parse_fecha("hasta", hoy),
        empleado_id=request.args.get("empleado_id", type=int),
        centro_trabajo=request.args.get("centro") or None,
        equipo_responsable_id=request.args.get("responsable_id", type=int),
    )
    filas = construir_informe_empleado(f)
    periodo = periodo_texto(f.fecha_inicio, f.fecha_fin)
    data = exportar_pdf(filas, "Informe de jornada", periodo)
    resp = make_response(data)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = "attachment; filename=informe_fichajes.pdf"
    return resp
