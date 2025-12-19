# TravelSphere — Cloud-Native Flight Pricing Platform

TravelSphere is a cloud-native backend that serves real-time flight pricing using the Amadeus Flight Offers API. The project is intentionally built end-to-end to mirror production concerns: configuration, containerization, orchestration, ingress, secrets, caching, and failure handling. It documents the decisions, trade-offs, and debugging steps that typically arise in real systems.

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

## Common Issues and Fixes (what actually happened)

1) Import errors when running Uvicorn
	- Symptom: `ModuleNotFoundError: No module named 'app'`
	- Fix: Switch to relative imports in [backend/app/main.py](backend/app/main.py).

2) Amadeus calls returning fallback
	- Causes: missing credentials, past departure dates, or Amadeus sandbox errors.
	- Fixes: load `.env`, add date parameter with future default, log HTTP errors for visibility.

3) Environment variables not seen in containers
	- Lesson: container/runtime env is isolated; pass with `--env-file` or Kubernetes `env`/Secrets.

4) Ingress 404s
	- Cause: host/header mismatch with NGINX ingress default backend.
	- Fix: ensure ingress host matches request or use port-forwarding during local tests.

5) Windows vs WSL DNS quirks
	- Browsers using DNS-over-HTTPS can bypass OS hosts; prefer curl inside WSL or set proper host headers.

---

## Roadmap (planned)

- GitHub Actions CI: lint, test, Docker build, push to registry
- Kubernetes Secrets for Amadeus credentials
- Coolify-based VPS deployment with HTTPS
- More endpoints (return trips, multi-city) and stronger validation

---

## How to Explain This Project

- Built a FastAPI service that integrates Amadeus with caching and graceful degradation.
- Containerized with a slim Dockerfile; runs the same locally and in-cluster.
- Kubernetes manifests showcase deployments, services, and ingress-style traffic flow.
- Observability via Prometheus metrics and structured error logging for third-party calls.
- Documented real-world debugging (imports, env propagation, ingress, DNS) to demonstrate production thinking.

---

## Author

Lakshaditya Singh — Cloud engineering, backend systems, Kubernetes, DevOps.

