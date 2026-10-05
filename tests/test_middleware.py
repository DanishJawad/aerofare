import json
import logging
import re

from app.commons.log_config import JsonFormatter, RequestIdFilter, request_id_var


def test_every_response_gets_a_generated_request_id(client):
    first = client.get("/airports").headers["X-Request-ID"]
    second = client.get("/airports").headers["X-Request-ID"]

    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert first != second


def test_a_valid_incoming_request_id_is_kept(client):
    r = client.get("/airports", headers={"X-Request-ID": "frontend-abc-123"})
    assert r.headers["X-Request-ID"] == "frontend-abc-123"


def test_an_unsafe_incoming_request_id_is_replaced(client):
    """Ids end up in log lines, so anything outside [A-Za-z0-9-] or longer
    than 64 characters is thrown away instead of being trusted."""
    for bad in ["has spaces", "x" * 65, "<script>"]:
        r = client.get("/airports", headers={"X-Request-ID": bad})
        assert r.headers["X-Request-ID"] != bad
        assert re.fullmatch(r"[0-9a-f]{32}", r.headers["X-Request-ID"])


def test_each_request_is_logged_once_with_status_and_duration(client, caplog):
    with caplog.at_level(logging.INFO, logger="aerofare.request"):
        client.get("/flights/999999")

    records = [r for r in caplog.records if r.name == "aerofare.request"]
    assert len(records) == 1
    record = records[0]
    assert record.method == "GET"
    assert record.path == "/flights/999999"
    assert record.status_code == 404
    assert record.duration_ms >= 0


def test_json_formatter_includes_the_request_id():
    token = request_id_var.set("req-42")
    try:
        record = logging.LogRecord("aerofare.request", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        record.status_code = 200
        RequestIdFilter().filter(record)
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert entry["request_id"] == "req-42"
    assert entry["message"] == "hello world"
    assert entry["status_code"] == 200
    assert entry["level"] == "INFO"
