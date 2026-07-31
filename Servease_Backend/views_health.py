"""Healthcheck endpoint — verifies DB, Redis, and Supabase connectivity."""
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.throttling import UserRateThrottle


class HealthRateThrottle(UserRateThrottle):
    scope = "health"
    rate = "60/minute"


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([HealthRateThrottle])
def health(request):
    """Return 200 if DB + Redis + Supabase are reachable, 503 otherwise."""
    status = 200
    checks = {}

    # 1. Database
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = str(exc)
        status = 503

    # 2. Redis (channel layer)
    try:
        import redis as redis_mod

        r = redis_mod.Redis.from_url(
            settings.REDIS_URL, socket_timeout=2, decode_responses=True
        )
        r.ping()
        r.connection_pool.disconnect()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = str(exc)
        status = 503

    # 3. Supabase Auth
    try:
        import requests

        resp = requests.get(
            f"{settings.SUPABASE_URL}/auth/v1/settings",
            headers={"apikey": settings.SUPABASE_ANON_KEY},
            timeout=3,
        )
        checks["supabase"] = "ok" if resp.status_code == 200 else f"HTTP {resp.status_code}"
        if resp.status_code != 200:
            status = 503
    except Exception as exc:
        checks["supabase"] = str(exc)
        status = 503

    return JsonResponse(
        {"status": "healthy" if status == 200 else "unhealthy", "checks": checks},
        status=status,
    )
