FROM python:3.11-buster as builder

RUN pip install poetry

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN touch README.md

RUN poetry install --no-root && rm -rf $POETRY_CACHE_DIR

FROM python:3.11-slim-buster as runtime

WORKDIR /app

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY iptracker ./iptracker

ENV APP_HOST=0.0.0.0 \
    APP_PORT=8080 \
    METRICS_PORT=9090 \
    REQUEST_TIMEOUT=600

ENTRYPOINT gunicorn --timeout ${REQUEST_TIMEOUT} --bind "${APP_HOST}:${APP_PORT}" "iptracker.app:start_server()"