.PHONY: help install build up down restart logs clean dev-backend dev-frontend migrate test

# Colors for terminal output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "$(BLUE)YouTube Video Question Generator - Makefile Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# ============================================================================
# Docker Commands
# ============================================================================

build: ## Build all Docker containers
	@echo "$(BLUE)Building Docker containers...$(NC)"
	docker compose build

up: ## Start all services (detached mode)
	@echo "$(BLUE)Starting all services...$(NC)"
	docker compose up -d
	@echo "$(GREEN)Services started!$(NC)"
	@echo "Frontend: http://localhost:5173"
	@echo "Backend API: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"

down: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(NC)"
	docker compose down

restart: ## Restart all services
	@echo "$(YELLOW)Restarting all services...$(NC)"
	docker compose restart

logs: ## Show logs for all services (follow mode)
	docker compose logs -f

logs-backend: ## Show backend logs
	docker compose logs -f backend

logs-frontend: ## Show frontend logs
	docker compose logs -f frontend

logs-db: ## Show database logs
	docker compose logs -f postgres

# ============================================================================
# Database Commands
# ============================================================================

migrate: ## Run database migrations
	@echo "$(BLUE)Running database migrations...$(NC)"
	docker compose exec backend alembic upgrade head
	@echo "$(GREEN)Migrations completed!$(NC)"

migrate-local: ## Run database migrations locally (without Docker)
	@echo "$(BLUE)Running database migrations locally...$(NC)"
	@if [ -d "backend/venv" ]; then \
		cd backend && ./venv/bin/alembic upgrade head; \
	else \
		cd backend && alembic upgrade head; \
	fi
	@echo "$(GREEN)Migrations completed!$(NC)"

migrate-rollback: ## Rollback last migration
	@echo "$(YELLOW)Rolling back last migration...$(NC)"
	docker compose exec backend alembic downgrade -1

migrate-rollback-local: ## Rollback last migration locally (without Docker)
	@echo "$(YELLOW)Rolling back last migration locally...$(NC)"
	@if [ -d "backend/venv" ]; then \
		cd backend && ./venv/bin/alembic downgrade -1; \
	else \
		cd backend && alembic downgrade -1; \
	fi

migrate-create: ## Create new migration (usage: make migrate-create MESSAGE="your message")
	@echo "$(BLUE)Creating new migration...$(NC)"
	docker compose exec backend alembic revision --autogenerate -m "$(MESSAGE)"

migrate-create-local: ## Create new migration locally (usage: make migrate-create-local MESSAGE="your message")
	@echo "$(BLUE)Creating new migration locally...$(NC)"
	@if [ -d "backend/venv" ]; then \
		cd backend && ./venv/bin/alembic revision --autogenerate -m "$(MESSAGE)"; \
	else \
		cd backend && alembic revision --autogenerate -m "$(MESSAGE)"; \
	fi

db-shell: ## Open PostgreSQL shell
	docker compose exec postgres psql -U postgres -d youtube_qa_db

# ============================================================================
# Development Commands
# ============================================================================

dev: ## Start development environment (builds and starts all services)
	@echo "$(BLUE)Starting development environment...$(NC)"
	docker compose up -d --build
	@echo "$(YELLOW)Waiting for services to be ready...$(NC)"
	@sleep 5
	@make migrate
	@echo "$(GREEN)Development environment ready!$(NC)"
	@echo "Frontend: http://localhost:5173"
	@echo "Backend API: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"

dev-local: ## Start services locally (without Docker)
	@echo "$(BLUE)Starting local development...$(NC)"
	@echo "$(YELLOW)Note: Ensure PostgreSQL and Ollama are running locally$(NC)"
	@make -j2 dev-backend dev-frontend

dev-backend: ## Run backend locally (without Docker)
	@echo "$(BLUE)Starting backend locally...$(NC)"
	@if [ -d "backend/venv" ]; then \
		echo "$(GREEN)Using virtual environment at backend/venv$(NC)"; \
		cd backend && ./venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000; \
	else \
		echo "$(YELLOW)No venv found, using system Python. Run 'make install-backend' first.$(NC)"; \
		cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000; \
	fi

dev-frontend: ## Run frontend locally (without Docker)
	@echo "$(BLUE)Starting frontend locally...$(NC)"
	cd frontend && npm run dev

# ============================================================================
# Installation Commands
# ============================================================================

install: ## Install dependencies for local development
	@echo "$(BLUE)Installing backend dependencies...$(NC)"
	@make install-backend
	@echo "$(BLUE)Installing frontend dependencies...$(NC)"
	@make install-frontend
	@echo "$(GREEN)Dependencies installed!$(NC)"

install-backend: ## Install backend dependencies only
	@echo "$(BLUE)Installing backend dependencies...$(NC)"
	@if [ ! -d "backend/venv" ]; then \
		echo "$(YELLOW)Creating virtual environment...$(NC)"; \
		cd backend && python3 -m venv venv; \
	fi
	@echo "$(GREEN)Installing dependencies in venv...$(NC)"
	cd backend && ./venv/bin/pip install -r requirements.txt -r requirements-dev.txt

install-frontend: ## Install frontend dependencies only
	@echo "$(BLUE)Installing frontend dependencies...$(NC)"
	cd frontend && npm install

# ============================================================================
# Testing Commands
# ============================================================================

test: ## Run all tests
	@echo "$(BLUE)Running tests...$(NC)"
	docker compose exec backend pytest

test-backend: ## Run backend tests
	@echo "$(BLUE)Running backend tests...$(NC)"
	docker compose exec backend pytest -v

test-frontend: ## Run frontend tests
	@echo "$(BLUE)Running frontend tests...$(NC)"
	cd frontend && npm test

# ============================================================================
# Cleaning Commands
# ============================================================================

clean: ## Stop containers and remove volumes
	@echo "$(RED)Stopping and removing all containers and volumes...$(NC)"
	docker compose down -v
	@echo "$(GREEN)Cleanup complete!$(NC)"

clean-all: ## Remove containers, volumes, and images
	@echo "$(RED)Removing all containers, volumes, and images...$(NC)"
	docker compose down -v --rmi all
	@echo "$(GREEN)Complete cleanup done!$(NC)"

prune: ## Remove unused Docker resources
	@echo "$(YELLOW)Removing unused Docker resources...$(NC)"
	docker system prune -f
	@echo "$(GREEN)Prune complete!$(NC)"

# ============================================================================
# Utility Commands
# ============================================================================

status: ## Show status of all services
	@echo "$(BLUE)Service Status:$(NC)"
	docker compose ps

shell-backend: ## Open shell in backend container
	docker compose exec backend /bin/bash

shell-frontend: ## Open shell in frontend container
	docker compose exec frontend /bin/sh

check-ollama: ## Check if Ollama is running and accessible
	@echo "$(BLUE)Checking Ollama status...$(NC)"
	@curl -s http://localhost:11434/api/tags > /dev/null && echo "$(GREEN)✓ Ollama is running$(NC)" || echo "$(RED)✗ Ollama is not running. Please start it with: ollama serve$(NC)"

ps: ## Show running containers
	docker compose ps

# ============================================================================
# Production Commands
# ============================================================================

prod-build: ## Build for production
	@echo "$(BLUE)Building production containers...$(NC)"
	docker compose -f docker compose.prod.yml build

prod-up: ## Start production environment
	@echo "$(BLUE)Starting production environment...$(NC)"
	docker compose -f docker compose.prod.yml up -d
	@echo "$(GREEN)Production environment started!$(NC)"

prod-down: ## Stop production environment
	@echo "$(YELLOW)Stopping production environment...$(NC)"
	docker compose -f docker compose.prod.yml down

prod-logs: ## Show production logs
	docker compose -f docker compose.prod.yml logs -f

# ============================================================================
# Quick Actions
# ============================================================================

quick-start: build up migrate ## Quick start (build, up, migrate)
	@echo "$(GREEN)Application is ready!$(NC)"
	@make status

restart-backend: ## Restart only backend service
	docker compose restart backend

restart-frontend: ## Restart only frontend service
	docker compose restart frontend

restart-db: ## Restart only database service
	docker compose restart postgres

# ============================================================================
# Information
# ============================================================================

info: ## Show application information
	@echo "$(BLUE)========================================$(NC)"
	@echo "$(BLUE)YouTube Video Question Generator$(NC)"
	@echo "$(BLUE)========================================$(NC)"
	@echo ""
	@echo "$(GREEN)Services:$(NC)"
	@echo "  Frontend:  http://localhost:5173"
	@echo "  Backend:   http://localhost:8000"
	@echo "  API Docs:  http://localhost:8000/docs"
	@echo "  Database:  localhost:5432"
	@echo ""
	@echo "$(GREEN)Useful Commands:$(NC)"
	@echo "  make dev        - Start development environment"
	@echo "  make logs       - View all logs"
	@echo "  make migrate    - Run database migrations"
	@echo "  make clean      - Stop and remove all containers"
	@echo ""
	@echo "$(YELLOW)Requirements:$(NC)"
	@echo "  - Ollama must be running: ollama serve"
	@echo "  - Pull model: ollama pull iKhalid/ALLaM:7b"
	@echo ""
