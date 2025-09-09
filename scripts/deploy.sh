#!/bin/bash
# Anzen Production Deployment Script
# Usage: ./scripts/deploy.sh [environment]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-production}"
COMPOSE_FILE="docker-compose.prod.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check environment file
    if [[ ! -f "$PROJECT_ROOT/.env.${ENVIRONMENT}" ]]; then
        log_error "Environment file .env.${ENVIRONMENT} not found"
        log_info "Please create .env.${ENVIRONMENT} with required variables"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Load environment variables
load_environment() {
    log_info "Loading environment variables for ${ENVIRONMENT}..."
    
    # Load environment-specific variables
    if [[ -f "$PROJECT_ROOT/.env.${ENVIRONMENT}" ]]; then
        export $(grep -v '^#' "$PROJECT_ROOT/.env.${ENVIRONMENT}" | xargs)
        log_success "Environment variables loaded"
    fi
}

# Pre-deployment checks
pre_deployment_checks() {
    log_info "Running pre-deployment checks..."
    
    # Check required environment variables
    required_vars=(
        "POSTGRES_PASSWORD"
        "REDIS_PASSWORD"
        "SECRET_KEY"
        "OPENAI_API_KEY"
        "GATEWAY_API_KEY"
    )
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            log_error "Required environment variable $var is not set"
            exit 1
        fi
    done
    
    # Check disk space
    available_space=$(df / | awk 'NR==2 {print $4}')
    required_space=5000000  # 5GB in KB
    
    if [[ $available_space -lt $required_space ]]; then
        log_error "Insufficient disk space. Required: 5GB, Available: $(($available_space/1024/1024))GB"
        exit 1
    fi
    
    log_success "Pre-deployment checks passed"
}

# Build images
build_images() {
    log_info "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build with BuildKit for better performance
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    docker-compose -f "$COMPOSE_FILE" build --parallel
    
    log_success "Docker images built successfully"
}

# Database initialization
init_database() {
    log_info "Initializing database..."
    
    cd "$PROJECT_ROOT"
    
    # Start only PostgreSQL first
    docker-compose -f "$COMPOSE_FILE" up -d postgres
    
    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    timeout=60
    while ! docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-anzen}" > /dev/null 2>&1; do
        sleep 2
        timeout=$((timeout - 2))
        if [[ $timeout -le 0 ]]; then
            log_error "PostgreSQL failed to start within 60 seconds"
            exit 1
        fi
    done
    
    # Run database migrations
    log_info "Running database migrations..."
    docker-compose -f "$COMPOSE_FILE" run --rm gateway python -c "
from anzen_gateway.database import DatabaseManager
from anzen_gateway.config import get_settings
settings = get_settings()
db = DatabaseManager(settings.database_url)
db.create_tables()
print('Database tables created successfully')
"
    
    log_success "Database initialized successfully"
}

# Deploy services
deploy_services() {
    log_info "Deploying Anzen services..."
    
    cd "$PROJECT_ROOT"
    
    # Start all services
    docker-compose -f "$COMPOSE_FILE" up -d
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    
    services=("gateway" "agent" "client")
    for service in "${services[@]}"; do
        log_info "Checking health of $service..."
        timeout=120
        while ! docker-compose -f "$COMPOSE_FILE" exec -T "$service" curl -f "http://localhost:$(get_service_port "$service")/health" > /dev/null 2>&1; do
            sleep 5
            timeout=$((timeout - 5))
            if [[ $timeout -le 0 ]]; then
                log_error "$service failed to become healthy within 120 seconds"
                docker-compose -f "$COMPOSE_FILE" logs "$service"
                exit 1
            fi
        done
        log_success "$service is healthy"
    done
    
    log_success "All services deployed successfully"
}

# Get service port
get_service_port() {
    case "$1" in
        "gateway") echo "8000" ;;
        "agent") echo "8001" ;;
        "client") echo "3000" ;;
        *) echo "8080" ;;
    esac
}

# Post-deployment verification
post_deployment_verification() {
    log_info "Running post-deployment verification..."
    
    cd "$PROJECT_ROOT"
    
    # Test API endpoints
    log_info "Testing API endpoints..."
    
    # Test gateway health
    if curl -f "http://localhost:8000/health" > /dev/null 2>&1; then
        log_success "Gateway health check passed"
    else
        log_error "Gateway health check failed"
        exit 1
    fi
    
    # Test agent health
    if curl -f "http://localhost:8001/health" > /dev/null 2>&1; then
        log_success "Agent health check passed"
    else
        log_error "Agent health check failed"
        exit 1
    fi
    
    # Test client health
    if curl -f "http://localhost:3000/health" > /dev/null 2>&1; then
        log_success "Client health check passed"
    else
        log_error "Client health check failed"
        exit 1
    fi
    
    # Test database connectivity
    if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-anzen}" > /dev/null 2>&1; then
        log_success "Database connectivity check passed"
    else
        log_error "Database connectivity check failed"
        exit 1
    fi
    
    log_success "Post-deployment verification completed"
}

# Cleanup old resources
cleanup() {
    log_info "Cleaning up old resources..."
    
    cd "$PROJECT_ROOT"
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes (be careful in production)
    # docker volume prune -f
    
    log_success "Cleanup completed"
}

# Show deployment status
show_status() {
    log_info "Deployment Status:"
    echo "===================="
    
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo ""
    log_info "Service URLs:"
    echo "- Web Dashboard: http://localhost:3000"
    echo "- API Gateway: http://localhost:8000"
    echo "- AI Agent: http://localhost:8001"
    echo "- Monitoring: http://localhost:3001 (Grafana)"
    echo "- Metrics: http://localhost:9090 (Prometheus)"
    
    echo ""
    log_info "Logs:"
    echo "- View logs: docker-compose -f $COMPOSE_FILE logs -f [service]"
    echo "- Available services: gateway, agent, client, postgres, redis, nginx"
}

# Main deployment function
main() {
    log_info "Starting Anzen deployment for environment: ${ENVIRONMENT}"
    echo "=================================================="
    
    check_prerequisites
    load_environment
    pre_deployment_checks
    build_images
    init_database
    deploy_services
    post_deployment_verification
    cleanup
    show_status
    
    echo ""
    log_success "🎉 Anzen deployment completed successfully!"
    log_info "The platform is now running and ready to use."
}

# Handle script interruption
trap 'log_error "Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"
