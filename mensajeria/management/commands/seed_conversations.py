"""
Per-domain seed: creates test conversations and messages.

Depends on seed_users having been run first (needs Usuario records).
Idempotent: skips if conversations already exist.

Usage:
    python manage.py seed_conversations [--force]
"""

# Stable UUIDs matching seed_users
import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from mensajeria.models import Conversacion, Mensaje
from usuarios.models import Usuario

_NS = uuid.UUID("00000000-0000-0000-0000-000000000000")

CONVERSACIONES = [
    {
        "cliente_uuid": uuid.uuid5(_NS, "cliente-juan-perez"),
        "proveedor_uuid": uuid.uuid5(_NS, "provider-sara-jimenez"),
        "mensajes": [
            "Hola Sara, necesito un cerrajero urgente. ¿Tienes disponibilidad hoy?",
            "Hola Juan, sí tengo disponibilidad. ¿Cuál es tu dirección?",
            "Genial, te la envío por aquí. ¿Cuánto cobras?",
        ],
    },
    {
        "cliente_uuid": uuid.uuid5(_NS, "cliente-carlos-lopez"),
        "proveedor_uuid": uuid.uuid5(_NS, "provider-sara-jimenez"),
        "mensajes": [
            "Buenos días Sara, vi tu perfil de plomería. ¿Haces reparaciones de tuberías?",
            "Buenos días Carlos, sí, todo tipo de reparaciones. ¿Qué necesitas?",
        ],
    },
]


class Command(BaseCommand):
    help = "Seed test conversations and messages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing seed conversations before recreating",
        )

    def handle(self, *args, **options):
        force = options["force"]
        tz = timezone.now()
        created = 0

        for conv_data in CONVERSACIONES:
            try:
                cliente = Usuario.objects.get(pk=conv_data["cliente_uuid"])
                proveedor = Usuario.objects.get(pk=conv_data["proveedor_uuid"])
            except Usuario.DoesNotExist as e:
                self.stderr.write(f"  SKIP: missing user — run seed_users first ({e})")
                continue

            if force:
                Conversacion.objects.filter(
                    cliente=cliente, proveedor=proveedor, servicio__isnull=True
                ).delete()

            conv, was_created = Conversacion.objects.get_or_create(
                cliente=cliente,
                proveedor=proveedor,
                servicio=None,
                defaults={"estado": "activa"},
            )

            if not was_created:
                self.stdout.write(f"  Exists:  conv #{conv.id_conversacion}")
                continue

            # Create messages with staggered timestamps
            for i, texto in enumerate(conv_data["mensajes"]):
                is_cliente = i % 2 == 0
                msg = Mensaje.objects.create(
                    conversacion=conv,
                    emisor=cliente if is_cliente else proveedor,
                    contenido=texto,
                    fecha=tz - timezone.timedelta(hours=len(conv_data["mensajes"]) - i),
                    leido=True,
                )
                conv.ultimo_mensaje_preview = texto[:200]
                conv.ultimo_mensaje_fecha = msg.fecha

            conv.save(update_fields=["ultimo_mensaje_preview", "ultimo_mensaje_fecha"])
            self.stdout.write(
                f"  Created: conv #{conv.id_conversacion} "
                f"({len(conv_data['mensajes'])} messages)"
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Seed conversations: {created} created"))
