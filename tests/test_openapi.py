import pytest
from fastapi import routing
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.authentication.dependencies import get_token_payload, require_admin
from app.main import app

SPEC = app.openapi()

# FastAPI keeps each include_router() as one wrapper object, so app.routes is
# not a flat list of endpoints. iter_route_contexts is what FastAPI's own
# OpenAPI generator walks; it yields every endpoint with its final path.
ROUTES = [
    ctx
    for ctx in routing.iter_route_contexts(app.routes)
    if isinstance(ctx.route, APIRoute) and ctx.route.include_in_schema
]


def _depends_on(dependant: Dependant, target) -> bool:
    return any(d.call is target or _depends_on(d, target) for d in dependant.dependencies)


def _operation(ctx) -> dict:
    (method,) = ctx.methods
    return SPEC["paths"][ctx.path_format][method.lower()]


def _id(ctx) -> str:
    return f"{next(iter(ctx.methods))} {ctx.path_format}"


def _error_statuses(operation: dict) -> set[int]:
    return {int(code) for code in operation["responses"] if int(code) >= 400}


def test_the_spec_covers_every_route():
    # Guards the test itself: if the route walk silently found nothing, every
    # parametrized test below would be skipped and pass without checking.
    assert len(ROUTES) >= 20
    assert len(ROUTES) == sum(len(methods) for methods in SPEC["paths"].values())


def test_fastapis_own_422_shape_is_gone():
    """The default HTTPValidationError describes a body this API no longer
    returns. Documenting it would send client authors the wrong way."""
    assert "HTTPValidationError" not in SPEC["components"]["schemas"]


@pytest.mark.parametrize("route", ROUTES, ids=_id)
def test_every_documented_error_uses_the_error_envelope(route):
    for code, response in _operation(route)["responses"].items():
        if int(code) >= 400:
            schema = response["content"]["application/json"]["schema"]
            assert schema == {"$ref": "#/components/schemas/ErrorResponse"}, f"{code}: {schema}"


@pytest.mark.parametrize("route", ROUTES, ids=_id)
def test_every_route_documents_422_and_500(route):
    assert {422, 500} <= _error_statuses(_operation(route))


@pytest.mark.parametrize("route", ROUTES, ids=_id)
def test_routes_that_need_login_document_401_and_503(route):
    if _depends_on(route.route.dependant, get_token_payload):
        assert {401, 503} <= _error_statuses(_operation(route)), (
            "this route requires a token, so it can return 401 (bad token) "
            "and 503 (Redis down); add them to its responses="
        )


@pytest.mark.parametrize("route", ROUTES, ids=_id)
def test_admin_routes_document_403(route):
    if _depends_on(route.route.dependant, require_admin):
        assert 403 in _error_statuses(_operation(route))


@pytest.mark.parametrize("route", ROUTES, ids=_id)
def test_every_route_has_a_description(route):
    assert _operation(route).get("description"), "add a one-line docstring"


def test_every_tag_in_use_is_described():
    described = {t["name"] for t in SPEC["tags"] if t.get("description")}
    used = {tag for r in ROUTES for tag in (r.route.tags or [])}
    assert used <= described, f"undescribed tags: {used - described}"
