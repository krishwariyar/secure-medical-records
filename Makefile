install-backend:
	cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
run-backend:
	cd backend && .venv/bin/uvicorn main:app --reload
run-frontend:
	cd frontend && npm run dev
