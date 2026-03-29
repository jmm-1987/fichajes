"""Tests de autenticación básica."""


def test_inicio_redirige_login(cliente):
    resp = cliente.get("/", follow_redirects=False)
    assert resp.status_code in (302, 301)


def test_login_formulario_disponible(cliente):
    resp = cliente.get("/autenticacion/iniciar-sesion")
    assert resp.status_code == 200
    assert b"Iniciar" in resp.data or b"Acceso" in resp.data
