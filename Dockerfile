FROM rust:1.99-bookworm@sha256:114c7a4425406451c2866b6aafe69fe29b1b298832db1277d411ac73c82d04d6 AS builder
ARG MBX_CACHE_BUILD_REVISION=unknown
ENV MBX_CACHE_BUILD_REVISION=$MBX_CACHE_BUILD_REVISION
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY migrations ./migrations
COPY src ./src
RUN cargo build --locked --release

# Coolify target: the distroless image below has no shell or HTTP client, so
# compose healthchecks and the retention sweeper have nothing to run. This
# variant adds curl and a shell and keeps the same non-root uid. Build it with
# `--target coolify`; the default (last) stage stays distroless.
FROM debian:bookworm-slim AS coolify
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 65532 nonroot \
    && useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin nonroot \
    && mkdir -p /var/lib/mbx-cache /var/tmp/mbx-cache \
    && chown 65532:65532 /var/lib/mbx-cache /var/tmp/mbx-cache
COPY --from=builder /src/target/release/mbx-cache /usr/local/bin/mbx-cache
ENV MBX_CACHE_DATA_DIR=/var/lib/mbx-cache \
    MBX_CACHE_LISTEN=0.0.0.0:7543 \
    TMPDIR=/var/tmp/mbx-cache
EXPOSE 7543
USER nonroot:nonroot
ENTRYPOINT ["/usr/local/bin/mbx-cache"]

FROM gcr.io/distroless/cc-debian12:nonroot@sha256:9dac0a79194e45a7da0158a9c6da57b217585af0786db3845d1f0ec1a0dd182f
COPY --from=builder /src/target/release/mbx-cache /usr/local/bin/mbx-cache
ENV MBX_CACHE_DATA_DIR=/tmp/mbx-cache
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/usr/local/bin/mbx-cache"]
