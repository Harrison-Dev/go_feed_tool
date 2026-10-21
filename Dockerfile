FROM golang:1.25-alpine AS build
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY cmd ./cmd
COPY internal ./internal
RUN gofmt -d cmd internal && test -z "$(gofmt -l cmd internal)"
RUN go test ./internal/handler ./cmd/server && go vet ./internal/handler ./cmd/server
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/feed-tool ./cmd/server

FROM alpine:3.22
RUN apk add --no-cache ca-certificates tzdata
WORKDIR /app
COPY --from=build /out/feed-tool /app/feed-tool
USER 65534:65534
EXPOSE 8080
CMD ["/app/feed-tool"]
