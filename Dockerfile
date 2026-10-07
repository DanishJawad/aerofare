# syntax=docker/dockerfile:1
FROM python:3.14-slim

# uv is copied in as a single binary from its official image, pinned to the
# version that wrote uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.10.6 /uv /bin/uv

# UV_LINK_MODE=copy: the build cache and the install target are on different
#   filesystems, so uv cannot hard-link and would only print warnings.
# UV_COMPILE_BYTECODE=1: compile .pyc files once at build time instead of on
#   the first import after every container start.
# UV_PYTHON_DOWNLOADS=0: use the Python from the base image, never download one.
# PATH: so `fastapi` and `alembic` resolve to the ones in the project's venv.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, in their own layer. They change rarely, so a code-only
# change rebuilds from the next step instead of reinstalling every package.
# --locked: fail if uv.lock and pyproject.toml disagree. --no-dev: no pytest.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

COPY pyproject.toml uv.lock alembic.ini ./
COPY app ./app
COPY migrations ./migrations
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Run as an unprivileged user: if the app is ever compromised, the attacker
# is not root inside the container.
RUN useradd --system --uid 10001 --no-create-home aerofare
USER aerofare

EXPOSE 8000
CMD ["fastapi", "run", "--port", "8000"]
