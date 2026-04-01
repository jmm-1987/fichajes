"""Persistencia de parámetros en `ConfiguracionAplicacion` y tablas auxiliares."""

from app.extensiones import db
from app.modelos import ConfiguracionAplicacion, ConfiguracionHorasNocturnas


def obtener_o_crear_config(clave: str, valor_defecto: str, tipo: str = "texto") -> ConfiguracionAplicacion:
    c = ConfiguracionAplicacion.query.filter_by(clave=clave).first()
    if not c:
        c = ConfiguracionAplicacion(clave=clave, valor=valor_defecto, tipo_valor=tipo)
        db.session.add(c)
        db.session.commit()
    return c


def establecer_config(clave: str, valor: str) -> None:
    c = ConfiguracionAplicacion.query.filter_by(clave=clave).first()
    if not c:
        c = ConfiguracionAplicacion(clave=clave, valor=valor, tipo_valor="texto")
        db.session.add(c)
    else:
        c.valor = valor
    db.session.commit()


def activar_configuracion_nocturna(hora_inicio, hora_fin) -> ConfiguracionHorasNocturnas:
    for fila in ConfiguracionHorasNocturnas.query.all():
        fila.activo = False
    nueva = ConfiguracionHorasNocturnas(
        hora_inicio=hora_inicio, hora_fin=hora_fin, activo=True
    )
    db.session.add(nueva)
    db.session.commit()
    return nueva


def obtener_config_empresa(
    empresa_id: int, clave: str, valor_defecto: str, tipo: str = "texto"
) -> ConfiguracionAplicacion:
    """
    Configuración laboral por empresa: clave namespaced por empresa.
    """
    clave_real = f"empresa:{empresa_id}:{clave}"
    return obtener_o_crear_config(clave_real, valor_defecto, tipo=tipo)


def establecer_config_empresa(empresa_id: int, clave: str, valor: str) -> None:
    """
    Guarda configuración laboral para una empresa concreta.
    """
    clave_real = f"empresa:{empresa_id}:{clave}"
    establecer_config(clave_real, valor)
