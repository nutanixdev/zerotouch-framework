# Multi-stage Dockerfile for ZTF
#
# Targets:
#   runtime       - Self-contained image: docker build --target runtime -t ztf:2.1.1 .
#   wheels-export - Offline wheel bundle: docker build --target wheels-export --output type=local,dest=./offline-wheels .
#
# Dark-site usage (offline pip install from exported wheels):
#   pip install --no-index --find-links=./offline-wheels --require-hashes -r ./offline-wheels/requirements.txt
#   pip install --no-index --find-links=./offline-wheels nutanix-ztf
#
# uv.lock is the single source of truth for dependency versions. The builder
# exports it to a hash-pinned requirements file at build time (not committed),
# and dependencies are installed with --require-hashes.

# ---------------------------------------------------------------------------
# Stage 1: builder — build the wheel and download all dependency wheels
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN pip install --no-cache-dir build

COPY pyproject.toml uv.lock README.md LICENSE.txt CHANGELOG.md ./
COPY ztf/ ./ztf/

RUN python -m build --wheel --outdir /build/dist \
    && uv export --frozen --no-dev --no-emit-project -o requirements.txt

RUN pip download \
    --dest=/wheels \
    --only-binary=:all: \
    --require-hashes \
    -r requirements.txt \
    && cp /build/dist/*.whl requirements.txt /wheels/

# ---------------------------------------------------------------------------
# Stage 2: runtime — minimal image with ZTF installed (no network needed)
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="ZTF" \
    org.opencontainers.image.description="Zero Touch Framework for Nutanix infrastructure automation" \
    org.opencontainers.image.licenses="Apache-2.0" \
    org.opencontainers.image.source="https://github.com/nutanixdev/zerotouch-framework"

COPY --from=builder /wheels /wheels

RUN pip install --no-cache-dir --no-index --find-links=/wheels \
    --require-hashes -r /wheels/requirements.txt \
    && pip install --no-cache-dir --no-index --find-links=/wheels \
    nutanix-ztf \
    && rm -rf /wheels

RUN useradd --create-home ztf
USER ztf
WORKDIR /home/ztf

ENTRYPOINT ["ztf"]
CMD ["--help"]

# ---------------------------------------------------------------------------
# Stage 3: wheels-export — scratch image for extracting offline wheels
# ---------------------------------------------------------------------------
FROM scratch AS wheels-export

COPY --from=builder /wheels /wheels/
