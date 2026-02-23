from django.core.cache import cache
from django.http import HttpRequest, JsonResponse

# Rate limit: 10 requests per 60 seconds per IP
RATE_LIMIT = 10
RATE_WINDOW = 60  # seconds


def get_client_ip(request: HttpRequest) -> str:
    """Extract the client IP address from the request.

    Handles X-Forwarded-For for reverse proxy setups.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Take the first IP (the original client)
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def check_rate_limit(
    request: HttpRequest, limit: int = RATE_LIMIT, window: int = RATE_WINDOW
) -> JsonResponse | None:
    """Check if the request should be rate limited.

    Returns None if the request is allowed, or a 429 JsonResponse if rate limited.
    """
    ip = get_client_ip(request)
    cache_key = f"nodl_auth_bridge:{ip}"

    count = cache.get(cache_key, 0)
    if count >= limit:
        response = JsonResponse(
            {"result": "error", "msg": "Rate limit exceeded", "code": "RATE_LIMIT_HIT"},
            status=429,
        )
        response["Retry-After"] = str(window)
        return response

    # Increment counter
    if count == 0:
        cache.set(cache_key, 1, timeout=window)
    else:
        # Use cache.incr for atomicity if available, with fallback
        try:
            cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, count + 1, timeout=window)

    return None
