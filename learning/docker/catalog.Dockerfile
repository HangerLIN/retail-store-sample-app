FROM docker.io/library/alpine:3.22@sha256:2e0b81d60597f449baa56dc25d355367869d2dca4cd57e866f1e2b52af3eb55f
RUN apk add --no-cache ca-certificates && adduser -D -u 1000 app
WORKDIR /app
COPY catalog /app/main
USER 1000:1000
ENV GIN_MODE=release
ENTRYPOINT ["/app/main"]
