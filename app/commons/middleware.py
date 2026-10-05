import logging
import re
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from .log_config import request_id_var

logger = logging.getLogger("aerofare.request")

REQUEST_ID_HEADER = "X-Request-ID"

# A caller (a gateway, the frontend, another service) may send its own id so
# one request can be traced across systems. It ends up in our logs, so only
# accept a short, plain value: anything else could be used to forge fake log
# lines (for example an id containing a newline).
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid4().hex
    # Not reset afterwards on purpose: each request runs in its own asyncio
    # task with its own copy of the context, so the value can't leak into
    # another request, and leaving it set lets the error handlers that run
    # after this function (step 2) still read it.
    request_id_var.set(request_id)

    start = time.perf_counter()
    status_code = 500  # if call_next raises, the client ends up with a 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.log(
            logging.ERROR if status_code >= 500 else logging.INFO,
            "%s %s -> %s in %sms",
            request.method,
            request.url.path,  # path only: query strings can carry data we shouldn't log
            status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )

    response.headers[REQUEST_ID_HEADER] = request_id
    return response
