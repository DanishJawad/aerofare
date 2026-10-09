from celery import Celery, signals

from app.commons.log_config import configure_logging, request_id_var
from app.database import settings

# The broker is the Redis the API already uses: the API pushes a task onto a
# list there and a worker process pops it off.
celery_app = Celery("aerofare", broker=settings.redis_url, include=["app.notifications.tasks"])

# Nothing reads a task's return value, so skip storing it (no result backend).
celery_app.conf.task_ignore_result = True

# The header that carries the API request's id to the worker. The API sets it
# when it queues a task (see notifications.tasks._enqueue).
REQUEST_ID_HEADER = "request_id"


@signals.setup_logging.connect
def _use_app_logging(**_: object) -> None:
    # Connecting to this signal stops Celery from installing its own log
    # format, so worker logs come out in the same pretty or JSON format as the
    # API's, with a request_id on every line.
    configure_logging(settings.log_level, settings.log_format)


@signals.task_prerun.connect
def _restore_request_id(task, **_: object) -> None:
    # Put the request id back into the same ContextVar the API uses, so every
    # log line written while this task runs carries it. A task queued outside
    # a request has no header and logs "-".
    # A worker exposes custom message headers as attributes of task.request;
    # eager mode (the tests) leaves them in task.request.headers. Check both.
    headers = task.request.headers or {}
    request_id = getattr(task.request, REQUEST_ID_HEADER, None) or headers.get(REQUEST_ID_HEADER) or "-"
    task.request._request_id_token = request_id_var.set(request_id)


@signals.task_postrun.connect
def _clear_request_id(task, **_: object) -> None:
    # A worker process runs many tasks one after another. Without this reset,
    # the next task would log the previous task's request id.
    token = getattr(task.request, "_request_id_token", None)
    if token is not None:
        request_id_var.reset(token)
