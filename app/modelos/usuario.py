"""Modelo de usuario del sistema (login y rol)."""

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensiones import db


def ahora_utc():
    """Marca temporal UTC con zona explícita."""
    return datetime.now(timezone.utc)


class Usuario(UserMixin, db.Model):
    """Usuario que puede iniciar sesión en la aplicación."""

    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    # Identificador único de acceso (usuario); el nombre de columna es histórico.
    correo_electronico = db.Column(
        db.String(255), unique=True, nullable=False, index=True
    )
    hash_contrasena = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(64), nullable=False, index=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    ultimo_acceso = db.Column(db.DateTime(timezone=True), nullable=True)
    intentos_fallidos_login = db.Column(db.Integer, nullable=False, default=0)
    bloqueado_hasta = db.Column(db.DateTime(timezone=True), nullable=True)
    token_recuperacion = db.Column(db.String(128), nullable=True, index=True)
    expira_token_recuperacion = db.Column(
        db.DateTime(timezone=True), nullable=True
    )
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc
    )
    actualizado_en = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        onupdate=ahora_utc,
    )

    empleado = db.relationship(
        "Empleado",
        back_populates="usuario",
        uselist=False,
    )

    def establecer_contrasena(self, contrasena_plana: str) -> None:
        """Genera y guarda el hash de la contraseña."""
        self.hash_contrasena = generate_password_hash(contrasena_plana)

    def verificar_contrasena(self, contrasena_plana: str) -> bool:
        """Comprueba la contraseña contra el hash almacenado."""
        return check_password_hash(self.hash_contrasena, contrasena_plana)
