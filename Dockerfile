# Reproducible environment for the Screen benchmark: Python 3.13.13 + Node 24.15.0 + pinned packages.
#   docker build -t screen-reproducible .
#   docker run --rm -v "$PWD/outputs:/work/outputs" screen-reproducible            # quick mode (default)
#   docker run --rm -v "$PWD/outputs:/work/outputs" screen-reproducible --full     # full run
FROM node:24.15.0-bookworm-slim AS node
FROM python:3.13.13-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 MPLBACKEND=Agg
WORKDIR /work
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Download + SHA-256-verify the Cohen datasets at build time so runs need no network.
RUN python bench/fetch_data.py
ENTRYPOINT ["python", "docker_entry.py"]
CMD ["--quick"]
