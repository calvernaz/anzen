# Anzen - Safe Agentic Workflows
# Development Makefile

.PHONY: help install test lint start-gateway start-agent start-client docker-up docker-down docker-logs clean

# Default target
help:
	@echo "Anzen Development Commands"
	@echo "========================="
	@echo ""
	@echo "Setup:"
	@echo "  install     Install all packages and dependencies"
	@echo ""
	@echo "Development:"
	@echo "  test        Run tests for all packages"
	@echo "  lint        Run linting and formatting"
	@echo "  clean       Clean build artifacts"
	@echo ""
	@echo "Services:"
	@echo "  start-gateway   Start the Safety Gateway (port 8000)"
	@echo "  start-agent     Start the AI Agent (port 8001)"
	@echo "  start-client    Start the Web Client (port 3001)"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up       Start all services with Docker Compose"
	@echo "  docker-down     Stop Docker Compose services"
	@echo "  docker-logs     Show Docker Compose logs"
	@echo ""
	@echo "Examples:"
	@echo "  make install && make start-gateway"
	@echo "  make docker-up"

# Installation
install:
	@echo "🔧 Installing all packages..."
	uv sync --dev

# Testing
test:
	@echo "🧪 Running tests..."
	uv run pytest packages/

test-gateway:
	@echo "🧪 Testing gateway..."
	cd packages/gateway && uv run pytest

test-agent:
	@echo "🧪 Testing agent..."
	cd packages/agent && uv run pytest

test-client:
	@echo "🧪 Testing client..."
	cd packages/client && uv run pytest

# Linting and formatting
lint:
	@echo "🔍 Running linting..."
	uv run black packages/
	uv run isort packages/
	@echo "✅ Code formatting complete!"

# Full linting with type checking (may have issues)
lint-full:
	@echo "🔍 Running full linting with type checking..."
	uv run black packages/
	uv run isort packages/
	uv run mypy packages/ || echo "⚠️  Type checking has issues but code is formatted"

# Start individual services
start-gateway:
	@echo "🚀 Starting Safety Gateway on port 8000..."
	cd packages/gateway && uv run anzen-gateway --log-level debug

start-agent:
	@echo "🚀 Starting AI Agent on port 8001..."
	cd packages/agent && uv run anzen-agent --log-level debug

start-client:
	@echo "🚀 Starting Web Client on port 3001..."
	cd packages/client && uv run anzen-client --port 3001 --log-level debug

# Start all services (for testing - use separate terminals for development)
start-all:
	@echo "🚀 Starting all Anzen services..."
	@echo "Note: This starts services sequentially. For development, use separate terminals."
	@echo "Gateway: http://localhost:8000"
	@echo "Agent: http://localhost:8001"
	@echo "Client: http://localhost:3001"
	@echo ""
	make start-gateway &
	sleep 3 && make start-agent &
	sleep 3 && make start-client

# Docker commands
docker-up:
	@echo "🐳 Starting all services with Docker Compose..."
	docker compose -f docker-compose.prod.yml up --build

docker-down:
	@echo "🐳 Stopping Docker Compose services..."
	docker compose -f docker-compose.prod.yml down

docker-logs:
	@echo "📋 Showing Docker Compose logs..."
	docker compose -f docker-compose.prod.yml logs -f

# Cleanup
clean:
	@echo "🧹 Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# Development workflow
dev-setup: install
	@echo "✅ Development setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Set your OpenAI API key: export OPENAI_API_KEY=your-key"
	@echo "2. Start services:"
	@echo "   Terminal 1: make start-gateway"
	@echo "   Terminal 2: make start-agent" 
	@echo "   Terminal 3: make start-client"
	@echo "3. Visit http://localhost:3001"

# Quick development start
dev: dev-setup
	@echo "🚀 Starting development environment..."
	@echo "Note: This will start services sequentially."
	@echo "For parallel execution, use separate terminals or 'make docker-up'"
