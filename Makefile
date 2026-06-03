# Convenience targets. Most workflows just need `make up`.

.PHONY: up down logs build backend-run frontend-dev helm-template k8s-apply

up: ## Build and start the full stack locally
	docker compose up --build

down: ## Stop and remove the stack
	docker compose down

logs: ## Tail all service logs
	docker compose logs -f

build: ## Build both images
	docker build -t quanta-backend:dev ./backend
	docker build -t quanta-frontend:dev ./frontend

backend-run: ## Run the backend locally (needs Go + a reachable Postgres/Redis)
	cd backend && go run ./cmd/api

frontend-dev: ## Run the Next.js dev server (needs Node)
	cd frontend && npm install && npm run dev

helm-template: ## Render the Helm chart to stdout
	helm template quanta ./deploy/helm/trading-dashboard

k8s-apply: ## Apply the raw manifests with kustomize
	kubectl apply -k ./deploy/k8s
