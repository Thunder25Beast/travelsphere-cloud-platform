# TravelSphere — Cloud-Native Flight Pricing Platform

TravelSphere is a cloud-native backend that serves real-time flight pricing using the Amadeus Flight Offers API. Unlike tutorial projects that stop at "it runs on my machine," this platform addresses production concerns end-to-end: configuration management, containerization, orchestration, secrets handling, caching strategies, failure recovery, and deployment automation.

## Why This Project Exists

Most backend projects demonstrate basic CRUD operations. This project answers different questions:
- How do real services integrate external APIs securely without leaking credentials?
- What happens when containers don't see the same environment as the host?
- Why does code that works locally fail in Docker or Kubernetes?
- How does traffic actually flow through ingress controllers and load balancers?
- Why is CI/CD mandatory for production systems rather than optional?

This repository documents not just the working solution, but the debugging journey, architecture decisions, and lessons learned from real-world failure modes.

---

## Key Features

- FastAPI backend with `/health`, `/search`, and `/metrics` endpoints
- Amadeus integration with graceful fallback and in-memory TTL cache
- Environment-driven configuration with `.env` support via python-dotenv
- Production-safe Dockerfile and Uvicorn gunicorn-style execution
- Kubernetes manifests (deployment, service, ingress) for cluster operation
- NGINX ingress-style routing to mirror cloud load balancers
- Metrics export using Prometheus client counters
- CI/CD ready structure (GitHub Actions + Docker registry planned)

---

## Architecture Overview

Client (browser or API consumer)
-> NGINX Ingress Controller
-> Kubernetes Service (ClusterIP)
-> FastAPI pods (replicas)
-> External Flight API (Amadeus)

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.12 |
| Framework | FastAPI |
| ASGI Server | Uvicorn |
| Reverse Proxy | NGINX |
| Container | Docker |
| Orchestration | Kubernetes (manifests provided) |
| Ingress | NGINX Ingress Controller |
| External API | Amadeus Flight Offers API |
| CI/CD | GitHub Actions (planned) |
| Deployment | VPS via Coolify (planned) |

---

## Project Layout

- [backend/app/main.py](backend/app/main.py) — FastAPI app, routing, metrics
- [backend/app/services/flights.py](backend/app/services/flights.py) — Amadeus client, caching, fallback
- [backend/requirements.txt](backend/requirements.txt) — Python dependencies
- [backend/Dockerfile](backend/Dockerfile) — Backend container image
- [k8s/deployment.yaml](k8s/deployment.yaml) — Deployment and probes
- [k8s/service.yaml](k8s/service.yaml) — ClusterIP service
- [.env.example](.env.example) — Sample environment configuration

---

## API

### GET /health
Health check used by probes.

Response:
```
{ "status": "ok" }
```

### GET /search
Fetch a flight offer price.

Query parameters:
- `origin` (IATA code, for example BOM)
- `destination` (IATA code, for example DEL)
- `date` (optional, ISO date YYYY-MM-DD; defaults to today + 14 days)

Example:
```
/search?origin=BOM&destination=DEL&date=2026-01-05
```

Successful response (live Amadeus):
```
{
  "origin": "BOM",
  "destination": "DEL",
  "price": 5271,
  "currency": "INR",
  "source": "amadeus",
  "cached": false
}
```

Fallback response (on error or missing credentials):
```
{
  "origin": "BOM",
  "destination": "DEL",
  "price": 5555,
  "currency": "INR",
  "source": "fallback",
  "cached": true
}
```

### GET /metrics
Prometheus metrics (counter for request volume and process metrics).

---

## Configuration and Secrets

Environment variables (required for live Amadeus calls):
- `AMADEUS_CLIENT_ID`
- `AMADEUS_CLIENT_SECRET`

Local setup with `.env`:
1) Copy `.env.example` to `.env`.
2) Fill the Amadeus sandbox keys.

The app loads `.env` via python-dotenv at startup. Never commit real secrets.

---

## Caching Strategy

- In-memory dict cache with 5-minute TTL
- Cache key: `origin-destination-date`
- Reduces external API calls and latency
- Keeps service stateless; safe for multiple pods when paired with short TTL

---

## Local Development

Prerequisites: Python 3.12, pip, optional virtualenv.

```bash
cd ~/projects/travelsphere-cloud-platform
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env  # fill in keys
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Smoke tests:
```bash
curl http://localhost:8000/health
curl "http://localhost:8000/search?origin=BOM&destination=DEL"
curl "http://localhost:8000/search?origin=BOM&destination=DEL&date=2026-01-05"
curl http://localhost:8000/metrics | head -n 20
```

---

## Docker Usage

Build and run locally:
```bash
cd ~/projects/travelsphere-cloud-platform
docker build -t travelsphere-backend -f backend/Dockerfile backend
docker run --rm -p 8000:8000 --env-file .env travelsphere-backend
```

Notes:
- The Dockerfile uses a slim base and caches dependencies for fast rebuilds.
- Ensure `.env` is provided at runtime; it is not baked into the image.

---

## Kubernetes (local kind or any cluster)

Apply manifests:
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

Provide secrets/config (simple env for dev clusters):
```bash
kubectl set env deployment/travelsphere-backend \
  AMADEUS_CLIENT_ID=$AMADEUS_CLIENT_ID \
  AMADEUS_CLIENT_SECRET=$AMADEUS_CLIENT_SECRET
```

Ingress (with NGINX ingress controller):
- Port-forward the controller locally for testing:
```bash
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80
```
- Then hit `http://localhost:8080/search?origin=BOM&destination=DEL`

Scaling:
```bash
kubectl scale deployment travelsphere-backend --replicas=4
```

---

## Observability

- `/metrics` exposes Prometheus metrics via `prometheus-client`
- `travelsphere_requests_total` counter increments per `/search` call
- Uvicorn logs surface Amadeus token and offers errors for fast debugging

---

## Error Handling and Fallbacks

- If env vars are missing, the service raises a clear error and returns fallback payloads to keep the API responsive.
- Token and offer fetches log HTTP status and body when failures occur.
- A deterministic fallback response helps clients degrade gracefully during outages or quota limits.

---

## Real-World Challenges Faced & Solutions

### 1. Docker Image Immutability
**Problem:** Code changes didn't reflect in running containers.  
**Root cause:** Docker images are immutable snapshots; local edits require rebuilds.  
**Solution:** Automated image rebuilds in CI/CD pipeline; validated the principle that containers enforce reproducible artifacts.

### 2. Environment Variable Isolation
**Problem:** Local shell environment variables weren't visible inside containers.  
**Root cause:** Container runtime has isolated environment; host exports don't propagate automatically.  
**Solution:** Explicit `--env-file` for Docker, `env` blocks in Kubernetes manifests, and ConfigMaps/Secrets for production.

### 3. Module Import Errors in Uvicorn
**Problem:** `ModuleNotFoundError: No module named 'app'` when running as `backend.app.main`.  
**Root cause:** Absolute imports assumed a top-level `app` package that didn't exist.  
**Solution:** Switched to relative imports (`.services.flights`) to match the actual module hierarchy.

### 4. Amadeus API Returning Fallback Responses
**Problem:** All searches returned static fallback data instead of live prices.  
**Root causes:**
- Missing `AMADEUS_CLIENT_ID` and `AMADEUS_CLIENT_SECRET` environment variables
- Hardcoded past departure dates (2025-12-15) causing 400 errors
- No error visibility in logs

**Solution:**
- Loaded `.env` via `python-dotenv` at app startup
- Added optional `date` parameter with intelligent default (today + 14 days)
- Logged HTTP status and response bodies for token/offer failures
- Validated credentials are present before making requests

### 5. Ingress 404 Errors
**Problem:** Valid URLs returned 404 via ingress controller.  
**Root cause:** Host header mismatch; NGINX ingress default backend rejects unknown hosts.  
**Solution:** Used port-forwarding for local validation; documented that production ingress requires proper DNS/host configuration.

### 6. Windows vs WSL DNS Behavior
**Problem:** Adding `travelsphere.local` to Windows hosts file didn't work in browser.  
**Root cause:** Modern browsers use DNS-over-HTTPS, bypassing OS hosts file.  
**Solution:** Used `curl` inside WSL for testing; documented that local Kubernetes differs from cloud DNS resolution.

### 7. GitHub Authentication with SSH
**Problem:** Git push failed with "invalid username or token" despite correct password.  
**Root cause:** GitHub deprecated password authentication for git operations.  
**Solution:** Generated SSH key pair, added public key to GitHub, configured git to use SSH globally for all GitHub repos.

Each of these issues represents a real gap between local development and production cloud systems—exactly the type of debugging that happens in actual engineering work.

---

## What This Project Demonstrates

**Cloud-Native Architecture**
- Designing stateless services that can scale horizontally
- External API integration with retry logic and graceful degradation
- Environment-based configuration for portability across environments

**Container & Orchestration Fundamentals**
- Production-safe Dockerfile with layer caching and minimal attack surface
- Kubernetes deployment patterns: replicas, probes, rolling updates
- Service discovery and load balancing via ClusterIP services
- Ingress-based traffic routing mirroring cloud load balancers

**Production Engineering Mindset**
- Understanding that "works on my machine" ≠ production-ready
- Debugging infrastructure issues, not just application code
- Knowing when and why CI/CD eliminates manual deployment risks
- Documentation that captures decisions and failure modes

**Real System Integration**
- OAuth2 client credentials flow for API authentication
- Caching strategies to reduce external API costs and latency
- Logging and metrics for observability in distributed systems
- Fallback mechanisms for reliability under failure conditions

This project was intentionally over-engineered for learning purposes. Every component exists to understand why modern cloud systems are designed the way they are.


## Author

**Lakshaditya Singh**  
Cloud Engineering | Backend Systems | Kubernetes | DevOps

This project reflects real-world engineering practices: understanding failure modes, debugging infrastructure, and building systems that are reliable, observable, and maintainable. Every issue documented here was encountered and solved during development—no shortcuts, no templates, just systematic problem-solving.

