from app.database import settings


def test_the_configured_frontend_origin_is_allowed(client):
    origin = settings.cors_origins[0]
    r = client.options(
        "/flights", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin


def test_an_unknown_origin_is_not_allowed(client):
    r = client.get("/flights", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
