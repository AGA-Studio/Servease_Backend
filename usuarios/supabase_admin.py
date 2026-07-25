from django.conf import settings
from supabase import create_client, Client

_admin_client: Client | None = None


def get_supabase_admin() -> Client:
    """Service-role client, full admin access. Used to create pre-confirmed
    auth users on signup and for server-side compensating actions (e.g.
    deleting an orphaned auth user)."""
    global _admin_client
    if _admin_client is None:
        _admin_client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return _admin_client
