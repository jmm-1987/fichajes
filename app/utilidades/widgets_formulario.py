"""Widgets de entrada en formato español (dd/mm/aaaa)."""

from wtforms.widgets import TextInput

from app.utilidades.fechas import FORMATO_FECHA, valor_fecha_hora_edicion


class EntradaFechaEspanola(TextInput):
    """Campo texto con valor dd/mm/aaaa."""

    def __call__(self, field, **kwargs):
        kwargs.setdefault("placeholder", "dd/mm/aaaa")
        kwargs.setdefault("autocomplete", "off")
        if field.data is not None:
            kwargs["value"] = field.data.strftime(FORMATO_FECHA)
        return super().__call__(field, **kwargs)


class EntradaFechaHoraEspanola(TextInput):
    """Campo texto con valor dd/mm/aaaa HH:MM:SS (hora local mostrada)."""

    def __call__(self, field, **kwargs):
        kwargs.setdefault("placeholder", "dd/mm/aaaa hh:mm:ss")
        kwargs.setdefault("autocomplete", "off")
        if field.data is not None:
            kwargs["value"] = valor_fecha_hora_edicion(field.data)
        return super().__call__(field, **kwargs)
