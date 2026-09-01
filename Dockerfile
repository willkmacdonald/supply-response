FROM node:22-bookworm-slim AS web-build
WORKDIR /build/apps/web
ARG VITE_ENTRA_TENANT_ID
ARG VITE_ENTRA_WEB_CLIENT_ID
ARG VITE_ENTRA_API_SCOPE
ARG VITE_ENTRA_REDIRECT_URI
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN test -n "${VITE_ENTRA_TENANT_ID}" \
    && test -n "${VITE_ENTRA_WEB_CLIENT_ID}" \
    && test -n "${VITE_ENTRA_API_SCOPE}" \
    && test -n "${VITE_ENTRA_REDIRECT_URI}" \
    && VITE_ENTRA_TENANT_ID=${VITE_ENTRA_TENANT_ID} \
       VITE_ENTRA_WEB_CLIENT_ID=${VITE_ENTRA_WEB_CLIENT_ID} \
       VITE_ENTRA_API_SCOPE=${VITE_ENTRA_API_SCOPE} \
       VITE_ENTRA_REDIRECT_URI=${VITE_ENTRA_REDIRECT_URI} \
       npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl unixodbc \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
       -o /tmp/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && rm /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install --yes --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps ./apps
COPY agents ./agents
COPY data ./data
COPY integrations ./integrations
COPY services ./services
COPY migrations ./migrations
COPY --from=web-build /build/apps/web/dist ./apps/api/static
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
