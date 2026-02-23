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

    # Atomic pattern: add initializes to 0 only if key doesn't exist (no-op otherwise),
    # then incr atomically bumps the counter. This eliminates the race window
    # between get and set that exists in the non-atomic get/compare/set pattern.
    cache.add(cache_key, 0, timeout=window)
    try:
        count = cache.incr(cache_key)
    except ValueError:
        # Cache backend doesn't support incr or key vanished; read-then-increment
        current = cache.get(cache_key, 0)
        count = current + 1
        cache.set(cache_key, count, timeout=window)

    if count > limit:
        response = JsonResponse(
            {"result": "error", "msg": "Rate limit exceeded", "code": "RATE_LIMIT_HIT"},
            status=429,
        )
        response["Retry-After"] = str(window)
        return response

    return None
