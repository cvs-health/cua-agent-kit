# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

FROM redgate/flyway:13 AS flyway
FROM ghcr.io/astral-sh/uv:0.13.5 AS uv
FROM mcr.microsoft.com/playwright/python:v1.64.1-noble

COPY --from=uv /uv /usr/local/bin/uv
COPY --from=flyway /flyway /opt/flyway
COPY --from=flyway /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="/app/.venv/bin:/opt/flyway:/opt/java/openjdk/bin:${PATH}"
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV FLYWAY_LOCATIONS=filesystem:/opt/flyway/sql FLYWAY_CONNECT_RETRIES=30
ENV FLYWAY_CLEAN_DISABLED=true FLYWAY_BASELINE_ON_MIGRATE=false
WORKDIR /app
ENV HOME=/home/app
RUN mkdir -p /home/app && chown -R 31337:31337 /home/app
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY sample_app/ ./sample_app/
RUN uv sync --locked --no-dev
COPY flyway/sql/ /opt/flyway/sql/
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN mkdir -p /app/artifacts && chown -R 31337:31337 /app/artifacts
USER 31337:31337
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
EXPOSE 8080
CMD ["cua-agent-run"]
