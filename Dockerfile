FROM golang:1.20-alpine

WORKDIR /app

# 複製 go mod 文件
COPY go.mod go.sum ./

# 下載依賴
RUN go mod download

# 複製源代碼
COPY . .

# 修改 package 名稱為 main
RUN sed -i 's/package feed/package main/g' main.go ptt_parser.go plurk_parser.go

# 編譯
RUN go build -o main .

# 暴露端口
EXPOSE 8080

# 運行
CMD ["./main"]
