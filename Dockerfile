# Builds the whole site as one service: the Python API also serves the built 3D web app.
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY ["NASA Project/api/requirements-deploy.txt", "./"]
RUN pip install --no-cache-dir -r requirements-deploy.txt
COPY ["NASA Project/echo_path", "./echo_path"]
COPY ["NASA Project/api", "./api"]
COPY ["NASA Project/data", "./data"]
COPY --from=web /web/dist ./web_dist
ENV ECHO_PATH_WEB_DIST=/app/web_dist
ENV PYTHONUNBUFFERED=1
RUN useradd --uid 1000 --create-home app
USER app
# Hosts such as Render set PORT themselves.
CMD ["sh", "-c", "exec python -m uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
