.PHONY: help build up down logs clean test-load-sync test-load-async seed restart status

# Default target
help:
	@echo "E-commerce Comparison - Makefile Commands"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make build          - Build all Docker images"
	@echo "  make up             - Start all services"
	@echo "  make up-sync        - Start services in sync mode"
	@echo "  make up-async       - Start services in async mode"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View logs from all services"
	@echo "  make logs-service   - View logs from specific service (SERVICE=name)"
	@echo "  make status         - Show status of all services"
	@echo "  make clean          - Remove all containers, volumes, and images"
	@echo ""
	@echo "Testing:"
	@echo "  make test-load-sync  - Run load test in sync mode"
	@echo "  make test-load-async - Run load test in async mode"
	@echo "  make locust          - Start Locust web UI"
	@echo ""
	@echo "Utilities:"
	@echo "  make seed            - Seed database with sample data"
	@echo "  make shell           - Open shell in service (SERVICE=name)"
	@echo "  make db-shell        - Open PostgreSQL shell"
	@echo ""
	@echo "URLs:"
	@echo "  UI:          http://localhost:8501"
	@echo "  API Gateway: http://localhost:8181"
	@echo "  Grafana:     http://localhost:3000 (admin/admin)"
	@echo "  Prometheus:  http://localhost:9090"
	@echo "  Jaeger:      http://localhost:16686"
	@echo "  RabbitMQ:    http://localhost:15692 (guest/guest)"
	@echo "  Locust:      http://localhost:8089"

# Build all Docker images
build:
	cd infra && docker-compose build

# Start all services (default: sync mode)
up:
	cd infra && docker-compose up -d

# Start services in sync mode
up-sync:
	cd infra && COMMUNICATION_MODE=sync docker-compose up -d

# Start services in async mode
up-async:
	cd infra && COMMUNICATION_MODE=async docker-compose up -d

# Stop all services
down:
	cd infra && docker-compose down

# Restart all services
restart:
	cd infra && docker-compose restart

# View logs
logs:
	cd infra && docker-compose logs -f

# View logs for specific service
logs-service:
	cd infra && docker-compose logs -f $(SERVICE)

# Show service status
status:
	cd infra && docker-compose ps

# Clean up everything
clean:
	cd infra && docker-compose down -v --rmi all --remove-orphans

# Run load test in sync mode
test-load-sync:
	@echo "Starting load test in SYNC mode..."
	cd infra && COMMUNICATION_MODE=sync docker-compose up -d
	sleep 10
	cd infra && docker-compose --profile load-test run --rm locust \
		-f /app/locustfile.py \
		--host http://api-gateway:8181 \
		--users 50 \
		--spawn-rate 5 \
		--run-time 2m \
		--headless \
		--csv=/app/results/sync

# Run load test in async mode
test-load-async:
	@echo "Starting load test in ASYNC mode..."
	cd infra && COMMUNICATION_MODE=async docker-compose up -d
	sleep 10
	cd infra && docker-compose --profile load-test run --rm locust \
		-f /app/locustfile.py \
		--host http://api-gateway:8181 \
		--users 50 \
		--spawn-rate 5 \
		--run-time 2m \
		--headless \
		--csv=/app/results/async

# Start Locust web UI
locust:
	cd infra && docker-compose --profile load-test up -d locust
	@echo "Locust UI available at http://localhost:8089"

# Seed database
seed:
	cd infra && docker-compose exec postgres psql -U ecommerce -d ecommerce -f /docker-entrypoint-initdb.d/init-db.sql

# Open shell in service
shell:
	cd infra && docker-compose exec $(SERVICE) /bin/sh

# Open PostgreSQL shell
db-shell:
	cd infra && docker-compose exec postgres psql -U ecommerce -d ecommerce

# Switch to sync mode
switch-sync:
	cd infra && COMMUNICATION_MODE=sync docker-compose up -d order-service api-gateway
	@echo "Switched to SYNC mode"

# Switch to async mode
switch-async:
	cd infra && COMMUNICATION_MODE=async docker-compose up -d order-service api-gateway
	@echo "Switched to ASYNC mode"
