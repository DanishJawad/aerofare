from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    # default=/onupdate= are client-side: SQLAlchemy computes the value in
    # Python and sends it as part of the INSERT/UPDATE, so it's always UTC
    # regardless of the MySQL server's configured timezone. server_default
    # stays only as a fallback for a row inserted outside the ORM - through
    # that path it *would* be the server's local NOW(), not UTC, but that's
    # not how this app writes rows.
    #
    # Without this, created_at (DB-side NOW()) and application-set UTC
    # timestamps like a payment's paid_at can disagree by the server's UTC
    # offset on the very same row.
    created_at: Mapped[datetime] = mapped_column(default=_utc_now, server_default=func.now())

    updated_at: Mapped[datetime] = mapped_column(
        default=_utc_now,
        onupdate=_utc_now,
        server_default=func.now(),
    )
