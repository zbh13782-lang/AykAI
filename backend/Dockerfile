FROM golang:1.25.4-alpine AS builder

WORKDIR /src
COPY . .

RUN go mod download && \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /out/gopherai ./main.go

FROM alpine:3.22

WORKDIR /app
RUN apk add --no-cache ca-certificates

COPY --from=builder /out/gopherai /app/gopherai
COPY config /app/config

EXPOSE 9030

CMD ["/app/gopherai"]
