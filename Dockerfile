FROM golang:1.21-alpine AS builder

WORKDIR /app

# Install necessary build tools
RUN apk add --no-cache git

# Copy go.mod and go.sum
COPY go.mod ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -o snmp-ai ./cmd/server

# Use a smaller image for the final stage
FROM alpine:latest

WORKDIR /app

# Install necessary runtime dependencies
RUN apk add --no-cache ca-certificates tzdata

# Copy the binary from the builder stage
COPY --from=builder /app/snmp-ai /app/
COPY --from=builder /app/configs /app/configs

# Create directory for MIBs
RUN mkdir -p /app/configs/mibs

# Set environment variables
ENV TZ=UTC

# Expose API port
EXPOSE 8080

# Run the application
CMD ["/app/snmp-ai"]
