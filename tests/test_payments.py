from decimal import Decimal

from .test_bookings import _make_flight


def test_booking_creates_a_completed_payment(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=10)
    booking = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 2}, headers=auth_headers
    ).json()

    payments = client.get("/payments/me", headers=auth_headers).json()
    assert len(payments) == 1
    assert payments[0]["booking_id"] == booking["id"]
    assert payments[0]["status"] == "completed"
    assert Decimal(str(payments[0]["amount"])) == Decimal(str(booking["total_amount"]))


def test_admin_refund_reverses_payment_booking_and_seats(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=10)
    booking = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 3}, headers=auth_headers
    ).json()
    payment = client.get("/payments/me", headers=auth_headers).json()[0]

    r = client.post(f"/payments/{payment['id']}/refund", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "refunded"

    booking_after = client.get(f"/bookings/{booking['id']}", headers=auth_headers).json()
    assert booking_after["status"] == "cancelled"
    assert client.get(f"/flights/{flight_id}").json()["available_seats"] == 10


def test_refunding_twice_is_rejected(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=10)
    client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 1}, headers=auth_headers
    )
    payment = client.get("/payments/me", headers=auth_headers).json()[0]

    client.post(f"/payments/{payment['id']}/refund", headers=admin_headers)
    r = client.post(f"/payments/{payment['id']}/refund", headers=admin_headers)
    assert r.status_code == 409


def test_non_admin_cannot_refund(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=10)
    client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 1}, headers=auth_headers
    )
    payment = client.get("/payments/me", headers=auth_headers).json()[0]

    r = client.post(f"/payments/{payment['id']}/refund", headers=auth_headers)
    assert r.status_code == 403
