from django.conf import settings
from supabase import create_client, Client

_anon_client: Client | None = None
_admin_client: Client | None = None


def get_supabase_anon() -> Client:
    """Public client, same privileges as the frontend. Used to trigger the
    normal signUp flow so Supabase sends the confirmation email itself."""
    global _anon_client
    if _anon_client is None:
        _anon_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _anon_client


def get_supabase_admin() -> Client:
    """Service-role client, full admin access. Only for server-side
    compensating actions (e.g. deleting an orphaned auth user)."""
    global _admin_client
    if _admin_client is None:
        _admin_client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return _admin_client
