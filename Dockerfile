FROM golang:1.25.14-alpine3.24@sha256:1ae0735f00daffa3aaf1363a5184c0d2dc55c78e3db4ec70241cdac97bf84b59 AS build
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
