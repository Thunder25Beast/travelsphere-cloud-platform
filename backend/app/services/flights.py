import os
import time
import datetime as _dt
import requests

AMADEUS_TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
AMADEUS_FLIGHT_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"
EXCHANGE_RATE_URL = "https://api.exchangerate-api.com/v4/latest/{currency}"

_cache = {}
_CACHE_TTL = 300  # 5 minutes
_exchange_cache = {}
_EXCHANGE_CACHE_TTL = 3600  # 1 hour (rates don't change that often)

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


def get_exchange_rate(from_currency: str, to_currency: str) -> float:
    """Fetch exchange rate with caching."""
    cache_key = f"{from_currency}-{to_currency}"
    
    if cache_key in _exchange_cache:
        rate, timestamp = _exchange_cache[cache_key]
        if time.time() - timestamp < _EXCHANGE_CACHE_TTL:
            return rate
    
    try:
        response = requests.get(
            EXCHANGE_RATE_URL.format(currency=from_currency),
            timeout=5,
        )
        response.raise_for_status()
        rates = response.json().get("rates", {})
        rate = rates.get(to_currency, 1.0)
        
        _exchange_cache[cache_key] = (rate, time.time())
        return rate
    except Exception as e:
        print(f"Exchange rate fetch error: {e}")
        # Return 1.0 as fallback (no conversion)
        return 1.0


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
    original_currency = data["price"]["currency"]

    # Convert to INR and EUR
    conversions = {}
    if original_currency != "INR":
        inr_rate = get_exchange_rate(original_currency, "INR")
        conversions["INR"] = {
            "amount": round(price * inr_rate, 2),
            "rate": round(inr_rate, 4)
        }
    
    if original_currency != "EUR":
        eur_rate = get_exchange_rate(original_currency, "EUR")
        conversions["EUR"] = {
            "amount": round(price * eur_rate, 2),
            "rate": round(eur_rate, 4)
        }

    result = {
        "origin": origin,
        "destination": destination,
        "price": {
            "original": {
                "amount": round(price, 2),
                "currency": original_currency
            },
            "conversions": conversions
        },
        "source": "amadeus",
    }

    _cache[cache_key] = (result, time.time())
    return {**result, "cached": False}
