FROM localhost:5001/bases/catalog@sha256:4df98fb6e5a283302fb1d9d5e5d2d33c195bebf9460d9419f625d1e32ba401ca
RUN apk add --no-cache ca-certificates && adduser -D -u 1000 app
WORKDIR /app
COPY catalog /app/main
USER 1000:1000
ENV GIN_MODE=release
ENTRYPOINT ["/app/main"]
