# CollegeLife

CollegeLife is a full-stack campus social app where students can sign in with Google, create media posts, and explore music, restaurants, and weather content.

## Project Overview

Core features:
- Google OAuth login with role-aware sessions.
- Posts CRUD (create, list, update, delete) with like/view interactions.
- Admin account management from account page.
- Supabase Database (user/post data)
- Cloudinary (media upload/storage)
- Spotify API (music page)
- Note: Spotify Premium is required for full current-track/playback access.
- Yelp API (restaurants page)
- OpenWeather API (weather page)

## Architecture

### Components
- Frontend: React + Vite (frontend)
- Backend API: Python Flask (backend)
- Database: Supabase PostgreSQL 
- Media store: Cloudinary
- External APIs: Spotify, Yelp, OpenWeather

### Layers
- UI layer (React pages/components): renders state, triggers API calls.
- API/controller layer (Flask routes): auth, validation, orchestration.
- Service/helper layer (backend/services/post_rules.py): business rules and reusable validation normalization.
- Data/integration layer: Supabase tables.

### Data Flow
1. User interacts in React page.
2. Frontend calls Flask endpoint with session credentials.
3. Flask authenticates/authorizes and validates payload.
4. Flask reads/writes Supabase and/or Cloudinary/3rd-party APIs.
5. Flask returns JSON; frontend updates UI.

## Tech Stack

- Frontend: React and Vite
- Backend: Python, Flask, Authlib, Supabase, Cloudinary SDK
- Observability: Prometheus metrics endpoint + Grafana dashboard assets
- CI/CD: GitHub Actions
- Containers: Docker 

## Run Locally

### 1) Prerequisites
- Python 3.13+
- Node 22+
- npm

### 2) Configure environment
- Copy .env.example to .env in repo root.
- Fill all required keys with your own credentials.

### 3) Start backend
1. cd backend
2. pip install -r requirements.txt
3. python3 main.py
Backend runs on http://localhost:8000

### 4) Start frontend
1. cd frontend
2. npm install
3. npm run dev
Frontend runs on http://localhost:5173

## Run with Docker

### Build images manually
1. docker build -f backend/Dockerfile -t collegelife-backend:local backend
2. docker build -f frontend/Dockerfile -t collegelife-frontend:local frontend

### Observability Stack 
docker compose -f docker-compose.observability.yml up --build
- Backend: http://localhost:8000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin / admin)

## CI/CD

Workflow file: .github/workflows/ci.yml

Pipeline behavior:
- Trigger on push and pull request to main
- Build and test backend.
- Build and test frontend.
- Run Playwright E2E.
- Build Docker images (backend + frontend).

Quality gate:
- Pipeline fails automatically if tests or coverage checks fail.

## Testing

### Backend unit + integration tests
1. cd backend
2. pytest -q

- Includes unit tests for helpers/business rules.
- Includes integration/API tests against real Flask routes with isolated fake test DB layer.
- Coverage gate configured in backend/pytest.ini (--cov=main --cov-fail-under=80).

### Frontend unit/component tests
1. cd frontend
2. npm run test
3. npm run test:coverage

- Coverage gate configured in frontend/vite.config.js.

### Frontend E2E tests
1. cd frontend
2. npx playwright install
3. npm run e2e

- Includes flows:
- login -> list -> detail
- login -> create new entity

Spotify requirement:
- The Music page requires a Spotify Premium account for reliable current-track and playback endpoints.

## Observability

Health endpoints:
- GET /health
- GET /health/live
- GET /health/ready

Metrics endpoint:
- GET /metrics

Key metrics:
- http_requests_total
- http_request_duration_seconds
- posts_created_total

Dashboard assets:
- monitoring/prometheus.yml
- monitoring/grafana/provisioning/datasources/prometheus.yml
- monitoring/grafana/provisioning/dashboards/dashboard.yml
- monitoring/grafana/dashboards/college-life-observability.json

## Credentials and Sample Data Instructions

- Never commit real secrets to Git.
- Use .env locally (already gitignored).
- Required secrets include:
- Google OAuth client id/secret
- Supabase URL + service role key
- Cloudinary keys
- Spotify/Yelp/Weather API keys

## Author

Wilson Quilli  
SWENG 861: Software Construction