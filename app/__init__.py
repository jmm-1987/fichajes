"""Factoría de aplicación Flask — control horario."""

from flask import Flask, render_template

from configuracion import Configuracion, ConfiguracionPruebas
from app.extensiones import csrf, db, login_manager, migrate
from app.modelos import Usuario


def crear_aplicacion(config_class=Configuracion) -> Flask:
    """Crea y configura la aplicación."""
    # Nombre `aplicacion_flask`: evita que `import app.modelos` haga que `app` deje de ser local
    # y el `return` devuelva por error el paquete `app`.
    aplicacion_flask = Flask(
        __name__,
        template_folder="plantillas",
        static_folder="static",
        static_url_path="/static",
    )
    aplicacion_flask.config.from_object(config_class)

    db.init_app(aplicacion_flask)
    migrate.init_app(aplicacion_flask, db)
    csrf.init_app(aplicacion_flask)
    login_manager.init_app(aplicacion_flask)

    @login_manager.user_loader
    def cargar_usuario(usuario_id: str):
        return Usuario.query.get(int(usuario_id))

    registrar_blueprints(aplicacion_flask)
    registrar_manejadores_error(aplicacion_flask)
    registrar_filtros_jinja(aplicacion_flask)

    @aplicacion_flask.context_processor
    def inyectar_config_plantillas():
        return {
            "planificacion_habilitada": aplicacion_flask.config.get(
                "HABILITAR_MODULO_PLANIFICACION", True
            ),
        }

    with aplicacion_flask.app_context():
        import app.modelos  # noqa: F401 — modelos para migraciones

        # Inicialización automática de la base de datos y datos demo
        # para despliegues sencillos (primer arranque / entornos SQLite).
        uri_bd = aplicacion_flask.config.get("SQLALCHEMY_DATABASE_URI", "")
        if uri_bd.startswith("sqlite:///"):
            db.create_all()
            # Asegurar columna responsable_usuario_id en empleados (actualizaciones en caliente)
            from sqlalchemy import text

            info_cols = db.session.execute(text("PRAGMA table_info(empleados);")).fetchall()
            nombres_cols = {fila[1] for fila in info_cols}
            if "responsable_usuario_id" not in nombres_cols:
                db.session.execute(
                    text(
                        "ALTER TABLE empleados ADD COLUMN responsable_usuario_id INTEGER"
                    )
                )
                db.session.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_empleados_responsable_usuario_id "
                        "ON empleados (responsable_usuario_id)"
                    )
                )
                db.session.commit()

            # Crear superadmin por defecto si no hay usuarios
            if not Usuario.query.first():
                admin = Usuario(
                    correo_electronico="superadmin",
                    rol="superadministrador",
                    activo=True,
                )
                admin.establecer_contrasena("Demo1234!")
                db.session.add(admin)
                db.session.commit()

    if aplicacion_flask.config.get("DETRAS_DE_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        aplicacion_flask.wsgi_app = ProxyFix(
            aplicacion_flask.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
            x_prefix=1,
        )

    return aplicacion_flask


def registrar_blueprints(app: Flask) -> None:
    """Registra blueprints por módulo."""
    from app.administracion import administracion_bp
    from app.autenticacion import autenticacion_bp
    from app.empleados import empleados_bp
    from app.fichajes import fichajes_bp
    from app.informes import informes_bp
    from app.inicio import inicio_bp
    from app.planificacion import planificacion_bp
    from app.vacaciones import vacaciones_bp

    app.register_blueprint(autenticacion_bp)
    app.register_blueprint(inicio_bp)
    app.register_blueprint(empleados_bp)
    app.register_blueprint(fichajes_bp)
    app.register_blueprint(vacaciones_bp)
    app.register_blueprint(informes_bp)
    app.register_blueprint(administracion_bp)
    if app.config.get("HABILITAR_MODULO_PLANIFICACION", True):
        app.register_blueprint(planificacion_bp)


def registrar_filtros_jinja(app: Flask) -> None:
    """Fechas en plantillas: dd/mm/aaaa y dd/mm/aaaa hh:mm[:ss]."""
    from app.utilidades.fechas import formatear_fecha, formatear_fecha_hora

    app.jinja_env.filters["fecha_es"] = formatear_fecha

    def _fecha_hora_filtro(valor, con_segundos: bool = True):
        return formatear_fecha_hora(valor, con_segundos=con_segundos)

    app.jinja_env.filters["fecha_hora_es"] = _fecha_hora_filtro


def registrar_manejadores_error(app: Flask) -> None:
    """Páginas de error en español."""

    @app.errorhandler(403)
    def prohibido(_):
        return render_template("errores/403.html"), 403

    @app.errorhandler(404)
    def no_encontrado(_):
        return render_template("errores/404.html"), 404

    @app.errorhandler(500)
    def error_servidor(_):
        return render_template("errores/500.html"), 500


def crear_aplicacion_pruebas():
    """App para pytest."""
    return crear_aplicacion(ConfiguracionPruebas)
