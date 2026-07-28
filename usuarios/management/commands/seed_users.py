"""
Per-domain seed: creates test users for local development with Supabase Auth.

Idempotent: safe to run multiple times. Creates Usuario and Rol entries.
Creates Supabase Auth users via two methods:
  1. Admin API (SUPABASE_SERVICE_ROLE_KEY) — for production/staging
  2. Signup endpoint (SUPABASE_ANON_KEY) — fallback for local dev

Usage:
    python manage.py seed_users [--force]
        --force: delete and recreate instead of get_or_create
"""
import uuid

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from usuarios.models import Rol, Usuario


# Stable UUIDs derived from a namespace UUID for reproducibility
_NS = uuid.UUID("00000000-0000-0000-0000-000000000000")

TEST_USERS = [
    {
        "uuid": uuid.uuid5(_NS, "cliente-juan-perez"),
        "nombre": "Juan",
        "segundo_nombre": "",
        "apellido_pa": "Perez",
        "apellido_ma": "",
        "correo": "cliente@test.com",
        "password": "test123",
        "celular": "6641234567",
        "rol_id": 1,  # client
        "estado": True,
    },
    {
        "uuid": uuid.uuid5(_NS, "provider-sara-jimenez"),
        "nombre": "Sara",
        "segundo_nombre": "",
        "apellido_pa": "Jimenez",
        "apellido_ma": "Garcia",
        "correo": "provider@test.com",
        "password": "test123",
        "celular": "6647654321",
        "rol_id": 2,  # provider
        "estado": True,
    },
    {
        "uuid": uuid.uuid5(_NS, "cliente-carlos-lopez"),
        "nombre": "Carlos",
        "segundo_nombre": "Alberto",
        "apellido_pa": "Lopez",
        "apellido_ma": "Martinez",
        "correo": "cliente2@test.com",
        "password": "test123",
        "celular": "6649876543",
        "rol_id": 1,  # client
        "estado": True,
    },
]


def _create_via_admin_api(email: str, password: str, user_id: str) -> bool | None:
    """Create a Supabase Auth user via admin API. Returns True/False or None if skipped."""
    service_key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not service_key or "placeholder" in service_key.lower() or "mock" in service_key.lower():
        return None  # no usable key

    url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"seed_uuid": user_id},
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 409:
            return False  # already exists
        if resp.status_code == 403:
            return None  # not authorized — caller should try signup endpoint
        resp.raise_for_status()
        return True
    except requests.RequestException:
        return None


def _create_via_signup(email: str, password: str, user_id: str) -> bool:
    """Create a Supabase Auth user via the signup endpoint (works with anon key on local dev)."""
    url = f"{settings.SUPABASE_URL}/auth/v1/signup"
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "password": password,
        "data": {"seed_uuid": user_id},
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code in (409, 422):
            return False  # already exists
        if resp.status_code == 200:
            return True
        return False
    except requests.RequestException:
        return False


class Command(BaseCommand):
    help = "Seed test users for local development (Supabase Auth)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing seed users before recreating",
        )
        parser.add_argument(
            "--skip-supabase",
            action="store_true",
            help="Skip creating Supabase Auth users",
        )

    def handle(self, *args, **options):
        force = options["force"]
        skip_supabase = options["skip_supabase"]

        # Ensure roles exist (idempotent)
        roles = {
            1: ("client", "Cliente"),
            2: ("provider", "Proveedor"),
            3: ("admin", "Administrador"),
        }
        for rid, (name, desc) in roles.items():
            Rol.objects.get_or_create(
                id_rol=rid, defaults={"nombre": name, "descripcion": desc}
            )

        created_count = 0
        supabase_count = 0
        for user_data in TEST_USERS:
            uid = user_data["uuid"]
            correo = user_data["correo"]

            if force:
                Usuario.objects.filter(pk=uid).delete()

            # Create or get Usuario
            usuario, was_created = Usuario.objects.get_or_create(
                pk=uid,
                defaults={
                    "nombre": user_data["nombre"],
                    "segundo_nombre": user_data.get("segundo_nombre", ""),
                    "apellido_pa": user_data["apellido_pa"],
                    "apellido_ma": user_data.get("apellido_ma", ""),
                    "correo": correo,
                    "celular": user_data.get("celular", ""),
                    "rol_id": user_data["rol_id"],
                    "estado": user_data.get("estado", True),
                },
            )

            if was_created:
                self.stdout.write(f"  Created: {correo} ({uid})")
                created_count += 1
            else:
                self.stdout.write(f"  Exists:  {correo}")

            # Create Supabase Auth user
            if not skip_supabase:
                result = _create_via_admin_api(
                    correo, user_data["password"], str(uid)
                )
                if result is None:
                    # Admin API not available — try signup endpoint (local dev)
                    result = _create_via_signup(
                        correo, user_data["password"], str(uid)
                    )
                if result:
                    self.stdout.write(f"  Supabase Auth user created: {correo}")
                    supabase_count += 1
                elif result is False:
                    self.stdout.write(f"  Supabase Auth user exists: {correo}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed users: {created_count} created, "
                f"{len(TEST_USERS) - created_count} already exist"
            )
        )
        if supabase_count:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Supabase Auth users created: {supabase_count}"
                )
            )
