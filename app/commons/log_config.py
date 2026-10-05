import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Literal

from rich.logging import RichHandler

# The id of the request currently being handled. A ContextVar is like a global
# that is private to each request: FastAPI handles many requests at once, and
# each one sees only the value it set. It also follows a sync route into the
# threadpool, because FastAPI copies the context when it hands work to a thread.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Fields the request middleware passes through `extra=` so the JSON output
# keeps them as separate keys instead of only inside the message text.
_EXTRA_FIELDS = ("method", "path", "status_code", "duration_ms")


class RequestIdFilter(logging.Filter):
    """Stamps every log record with the current request id.

    Attached to the handler rather than a logger, so it also covers records
    from libraries (uvicorn, SQLAlchemy) that propagate up to the root."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: easy for log tools to search and filter."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def configure_logging(level: str, fmt: Literal["pretty", "json"]) -> None:
    handler: logging.Handler
    if fmt == "json":
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
    else:
        handler = RichHandler(show_path=False, rich_tracebacks=True, log_time_format="[%X]")
        # %(request_id).8s prints the first 8 characters: enough to tell
        # requests apart while reading, without a 32-character id on every line.
        handler.setFormatter(logging.Formatter("%(request_id).8s  %(message)s"))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn installs its own handlers before importing the app. Remove them
    # so its startup and error messages go through our handler like
    # everything else. Its access log is switched off entirely, because the
    # request middleware writes a better line for every request.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
