from fastapi import FastAPI
from dotenv import load_dotenv
from prometheus_client import Counter, generate_latest
from fastapi.responses import Response
from .services.flights import get_flight_price
from fastapi import HTTPException
app = FastAPI(title="TravelSphere API")

# Load environment variables (for Amadeus keys, etc.)
load_dotenv()

REQUEST_COUNT = Counter(
    "travelsphere_requests_total",
    "Total requests to TravelSphere API"
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
def search(origin: str, destination: str, date: str | None = None):
    REQUEST_COUNT.inc()
    try:
        return get_flight_price(origin, destination, departure_date=date)
    except Exception as e:
        # Log the error and return fallback to keep the API responsive
        print("Search error:", repr(e))
        return {
            "origin": origin,
            "destination": destination,
            "price": {
                "original": {
                    "amount": 5555,
                    "currency": "INR"
                },
                "conversions": {}
            },
            "source": "fallback",
            "cached": True,
        }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
