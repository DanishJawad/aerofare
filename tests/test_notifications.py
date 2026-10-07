import smtplib
from email.message import EmailMessage

from app.notifications import mailer, tasks
from app.notifications.tasks import send_booking_confirmation
from app.worker import celery_app

from .conftest import Mail


def _book(client, headers, flight_id, seats=2, key=None):
    extra = {"Idempotency-Key": key} if key else {}
    return client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": seats}, headers={**headers, **extra}
    )


def test_booking_sends_a_confirmation_email(client, auth_headers, flight_id, mail_outbox):
    r = _book(client, auth_headers, flight_id, seats=2)
    assert r.status_code == 201

    assert len(mail_outbox) == 1
    mail = mail_outbox[0]
    assert mail.to == "user@example.com"
    assert mail.subject == "Booking confirmed: Lahore to Karachi"
    assert f"booking #{r.json()['id']}" in mail.text
    assert "Seats: 2 (economy)" in mail.text
    assert "Total paid: 300.00" in mail.text  # 2 * 150.00
    # The HTML version carries the same facts.
    assert "Seats" in mail.html and "2 (economy)" in mail.html and "300.00" in mail.html


def test_failed_booking_sends_nothing(client, auth_headers, flight_id, mail_outbox):
    assert _book(client, auth_headers, flight_id, seats=99).status_code == 409
    assert mail_outbox == []


def test_replayed_booking_does_not_send_a_second_email(client, auth_headers, flight_id, mail_outbox):
    assert _book(client, auth_headers, flight_id, key="k1").status_code == 201
    assert _book(client, auth_headers, flight_id, key="k1").status_code == 200
    assert len(mail_outbox) == 1


def test_booking_succeeds_even_if_the_email_cannot_be_queued(
    client, auth_headers, flight_id, mail_outbox, monkeypatch
):
    def broker_down(booking_id):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(tasks.send_booking_confirmation, "delay", broker_down)

    r = _book(client, auth_headers, flight_id)
    assert r.status_code == 201
    assert client.get(f"/flights/{flight_id}").json()["available_seats"] == 8
    assert mail_outbox == []


def test_no_email_if_the_booking_was_cancelled_before_the_task_ran(
    client, auth_headers, flight_id, mail_outbox
):
    booking_id = _book(client, auth_headers, flight_id).json()["id"]
    mail_outbox.clear()
    client.post(f"/bookings/{booking_id}/cancel", headers=auth_headers)

    send_booking_confirmation.delay(booking_id)
    assert mail_outbox == []


def test_unknown_booking_is_skipped_without_error(mail_outbox):
    send_booking_confirmation.delay(999999)
    assert mail_outbox == []


# Both retry tests turn off eager_propagates: with it on, Celery re-raises the
# first failure instead of running the retries, so the loop would never be seen.


def test_task_retries_when_the_mail_server_is_down(
    client, auth_headers, flight_id, mail_outbox, monkeypatch
):
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", False)
    booking_id = _book(client, auth_headers, flight_id).json()["id"]
    mail_outbox.clear()

    attempts = []

    def flaky(to, subject, text, html=None):
        attempts.append(1)
        if len(attempts) < 3:
            raise smtplib.SMTPServerDisconnected("server went away")
        mail_outbox.append(Mail(to, subject, text, html))

    monkeypatch.setattr(tasks, "send_email", flaky)
    result = send_booking_confirmation.apply(args=[booking_id])

    assert result.successful()
    assert len(attempts) == 3
    assert len(mail_outbox) == 1


def test_task_gives_up_after_three_retries(client, auth_headers, flight_id, monkeypatch):
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", False)
    booking_id = _book(client, auth_headers, flight_id).json()["id"]
    attempts = []

    def always_down(to, subject, text, html=None):
        attempts.append(1)
        raise smtplib.SMTPServerDisconnected("still down")

    monkeypatch.setattr(tasks, "send_email", always_down)
    result = send_booking_confirmation.apply(args=[booking_id])

    assert result.failed()
    assert isinstance(result.result, smtplib.SMTPServerDisconnected)
    assert len(attempts) == 4  # the first try plus 3 retries


def test_a_bug_in_the_task_is_not_retried(client, auth_headers, flight_id, monkeypatch):
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", False)
    booking_id = _book(client, auth_headers, flight_id).json()["id"]
    attempts = []

    def buggy(to, subject, text, html=None):
        attempts.append(1)
        raise ValueError("not a mail-server problem")

    monkeypatch.setattr(tasks, "send_email", buggy)
    result = send_booking_confirmation.apply(args=[booking_id])

    assert result.failed()
    assert len(attempts) == 1


def test_send_email_builds_the_message_and_sends_it(monkeypatch):
    captured: dict = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            captured.update(host=host, port=port, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def send_message(self, message: EmailMessage):
            captured["message"] = message

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    mailer.send_email("a@example.com", "Hi", "Body text", "<p>Body html</p>")

    message = captured["message"]
    assert message["To"] == "a@example.com"
    assert message["Subject"] == "Hi"
    assert message["From"] == mailer.settings.mail_from
    # One email, two versions: the mail client picks the best one it can show.
    assert message.get_content_type() == "multipart/alternative"
    assert message.get_body(("plain",)).get_content().strip() == "Body text"
    assert message.get_body(("html",)).get_content().strip() == "<p>Body html</p>"
    assert captured["timeout"] == 10


def test_names_are_escaped_in_the_html_email_but_not_in_the_text_one(
    client, flight_id, mail_outbox
):
    client.post(
        "/users/signup",
        json={"name": "<b>Mallory</b> & co", "email": "m@example.com", "password": "password123",
              "phone_number": None, "city": "Lahore", "country": "PK"},
    )
    token = client.post("/users/login", data={"username": "m@example.com", "password": "password123"}).json()
    _book(client, {"Authorization": f"Bearer {token['access_token']}"}, flight_id)

    mail = mail_outbox[0]
    assert "<b>Mallory</b>" not in mail.html
    assert "&lt;b&gt;Mallory&lt;/b&gt; &amp; co" in mail.html
    assert "Hello <b>Mallory</b> & co," in mail.text
