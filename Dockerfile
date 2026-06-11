# Multi-stage Dockerfile for ZTF
#
# Targets:
#   runtime       - Self-contained image: docker build --target runtime -t ztf:2.0.0 .
#   wheels-export - Offline wheel bundle: docker build --target wheels-export --output type=local,dest=./offline-wheels .
#
# Dark-site usage (offline pip install from exported wheels):
#   pip install --no-index --find-links=./offline-wheels nutanix-ztf

# ---------------------------------------------------------------------------
# Stage 1: builder — build the wheel and download all dependency wheels
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir build

COPY pyproject.toml README.md LICENSE.txt CHANGELOG.md ./
COPY ztf/ ./ztf/

RUN python -m build --wheel --outdir /build/dist

RUN pip wheel \
    --wheel-dir=/wheels \
    --find-links=/build/dist \
    /build/dist/*.whl

# ---------------------------------------------------------------------------
# Stage 2: runtime — minimal image with ZTF installed (no network needed)
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="ZTF" \
    org.opencontainers.image.description="Zero Touch Framework for Nutanix infrastructure automation" \
    org.opencontainers.image.licenses="Apache-2.0" \
    org.opencontainers.image.source="https://github.com/nutanixdev/zerotouch-framework"

COPY --from=builder /wheels /wheels

RUN pip install --no-cache-dir --no-index --find-links=/wheels nutanix-ztf \
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
