import os
import time
import datetime as _dt
import requests

AMADEUS_TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
AMADEUS_FLIGHT_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"

_cache = {}
_CACHE_TTL = 300  # 5 minutes

def get_access_token():
    client_id = os.getenv("AMADEUS_CLIENT_ID")
    client_secret = os.getenv("AMADEUS_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("Missing AMADEUS_CLIENT_ID or AMADEUS_CLIENT_SECRET")

    response = requests.post(
        AMADEUS_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=10,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        # Surface error details in logs for easier debugging
        print("Amadeus token error:", response.status_code, response.text)
        raise
    return response.json().get("access_token")


def get_flight_price(origin: str, destination: str, departure_date: str | None = None):
    cache_key = f"{origin}-{destination}-{departure_date or ''}"

    if cache_key in _cache:
        cached_data, timestamp = _cache[cache_key]
        if time.time() - timestamp < _CACHE_TTL:
            return {**cached_data, "cached": True}

    # Ensure the departure date is valid: default to 14 days from today if not provided
    if not departure_date:
        departure_date = (_dt.date.today() + _dt.timedelta(days=14)).isoformat()

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": departure_date,
        "adults": 1,
        "max": 1,
    }

    response = requests.get(
        AMADEUS_FLIGHT_URL,
        headers=headers,
        params=params,
        timeout=10,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError:
        print("Amadeus flight offers error:", response.status_code, response.text)
        raise

    data = response.json()["data"][0]
    price = float(data["price"]["total"])

    result = {
        "origin": origin,
        "destination": destination,
        "price": int(price),
        "currency": data["price"]["currency"],
        "source": "amadeus",
    }

    _cache[cache_key] = (result, time.time())
    return {**result, "cached": False}
