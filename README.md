# SEMER

Initial project structure for SEMER ECOMMERCE MARKETING PRIVATE LIMITED.

This repository has two applications:

- `frontend` — React, Vite, TypeScript, React Router, Axios, and Tailwind CSS
- `backend` — FastAPI

Authentication and the product catalog API are implemented. Checkout, travel, and events are not. The database schema is managed with Alembic.

The API reads `DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, and `JWT_ALGORITHM` from `backend/.env`. Credentials are not stored in the repository.

## Requirements

- Node.js 20 or newer
- Python 3.10 or newer

## Install

From the repository root:

```bash
cd frontend
npm install
```

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

```bash
# Git Bash on Windows
source .venv/Scripts/activate

# macOS or Linux
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

Environment files:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Set `DATABASE_URL` and `SECRET_KEY` in `backend/.env`, then apply the schema:

```bash
cd backend
alembic upgrade head
```

## Run the backend

From `backend`, with the virtual environment active:

```bash
uvicorn app.main:app --reload
```

API: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Run the frontend

From `frontend`:

```bash
npm run dev
```

App: [http://localhost:5173](http://localhost:5173)

The shop, product, and account pages call the API through `VITE_API_BASE_URL`. Set that to the API origin, for example `http://localhost:8000`.

## Checks

```bash
cd backend
pytest
```

```bash
cd frontend
npm run lint
npm run build
```
