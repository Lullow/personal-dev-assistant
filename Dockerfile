FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY config.yaml .env.example ./
COPY demo_project ./demo_project
COPY prompts ./prompts

RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

# Default command runs the deterministic demo (no API key required).
CMD ["personal-dev-assistant-demo", "--project-root", "/app"]
