.PHONY: install start-backend start-frontend eval stability-test migrate

# ==========================================
# CodeSentinel AI - Shortcuts
# ==========================================

# Install all dependencies (backend and frontend)
install:
	@echo "Installing backend dependencies..."
	cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Start the Django backend server
start-backend:
	@echo "Starting Django server on port 8000..."
	cd backend && source .venv/bin/activate && python manage.py runserver

# Start the React frontend server
start-frontend:
	@echo "Starting Vite frontend server..."
	cd frontend && npm run dev

# Run database migrations
migrate:
	@echo "Running Django migrations..."
	cd backend && source .venv/bin/activate && python manage.py makemigrations && python manage.py migrate

# ==========================================
# Evaluation Scripts
# ==========================================

# Run a single evaluation against the 10-defect dataset
eval:
	@echo "Running single evaluation (HEAD~2)..."
	source backend/.venv/bin/activate && python evals/run_eval.py --base-ref HEAD~2

# Run the evaluation 3 times back-to-back to test LLM stability
stability-test:
	@echo "Running stability test (3 runs)..."
	source backend/.venv/bin/activate && python evals/stability_test.py --base-ref HEAD~2 --runs 3
