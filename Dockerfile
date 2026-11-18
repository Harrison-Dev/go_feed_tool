FROM golang:1.26.11-alpine3.24@sha256:ecb67f987aa1a57794c91d19ade7ae0209f2f0f5496aaef9e6ae85ddf92d02ab AS build
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY cmd ./cmd
COPY internal ./internal
RUN gofmt -d cmd internal && test -z "$(gofmt -l cmd internal)"
RUN go test ./internal/handler ./cmd/server && go vet ./internal/handler ./cmd/server
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/feed-tool ./cmd/server

FROM alpine:3.22.6@sha256:5291449c3df73caf6ed85e649dec1b9e818b39a5d8c871e97afc13e9cd5e8fa8
# Base stays digest-pinned; pick up Alpine security fixes released since the base was built.
RUN apk upgrade --no-cache
RUN apk add --no-cache ca-certificates tzdata
WORKDIR /app
COPY --from=build /out/feed-tool /app/feed-tool
USER 65534:65534
EXPOSE 8080
CMD ["/app/feed-tool"]
