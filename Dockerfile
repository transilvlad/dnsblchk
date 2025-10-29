# Use a slim Python base image
FROM python:3.13-slim

ARG APP_NAME=dnsblchk
ARG APP_DIR=/app
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# OCI labels (metadata-action in workflow will also add labels; these are fallbacks).
LABEL org.opencontainers.image.title="DNSBL Checker" \
      org.opencontainers.image.description="A DNS Blacklist Checker service." \
      org.opencontainers.image.licenses="MIT"

# Install minimal OS deps.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create application directory and non-root user.
RUN useradd -m -d ${APP_DIR} -s /bin/bash appuser \
    && mkdir -p ${APP_DIR}/config ${APP_DIR}/logs

WORKDIR ${APP_DIR}

# Copy dependency manifests first for layer caching.
COPY pyproject.toml requirements.txt setup.py MANIFEST.in README.md LICENSE ./
# Copy source modules and config directory.
COPY *.py ./
COPY config ./config

# Install Python dependencies and the package (console script dnsblchk).
RUN pip install --upgrade pip \
    && if [ -f requirements.txt ]; then pip install -r requirements.txt; fi \
    && pip install . \
    && rm -rf ~/.cache/pip

# Ensure ownership for runtime write access when volumes aren't mounted.
RUN chown -R appuser:appuser ${APP_DIR}

# Declare volumes for external config & logs persistence.
VOLUME ["/app/config", "/app/logs"]

# Switch to non-root user.
USER appuser

# Entrypoint uses the installed console script.
ENTRYPOINT ["dnsblchk"]
CMD []
