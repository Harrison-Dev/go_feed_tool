FROM golang:1.24-alpine

WORKDIR /app

# 複製 go mod 文件
COPY go.mod go.sum ./

# 下載依賴
RUN go mod download

# 複製源代碼
COPY . .

# 編譯
RUN go build -o main ./cmd/server

# 暴露端口
EXPOSE 8080

# 運行
CMD ["./main"]
