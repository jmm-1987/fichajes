"""Extensiones Flask compartidas (inicialización diferida en la factory)."""

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "autenticacion_bp.iniciar_sesion"
login_manager.login_message = "Inicie sesión para acceder."
login_manager.login_message_category = "aviso"
